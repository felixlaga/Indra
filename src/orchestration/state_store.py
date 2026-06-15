"""In-memory state persistence for the research loop."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import LoopState, Branch

logger = logging.getLogger(__name__)


class StateStore:
    """
    In-memory state store for research loops.

    Provides:
    - In-memory storage of loop states
    - Optional persistence to disk (JSON)
    - State versioning and snapshots
    """

    def __init__(
        self,
        persist_path: Path | None = None,
        auto_persist: bool = False,
    ):
        """
        Initialize the state store.

        Args:
            persist_path: Optional path for disk persistence
            auto_persist: Whether to auto-save on every update
        """
        self._states: dict[str, LoopState] = {}
        self._snapshots: dict[str, list[dict]] = {}  # loop_id -> list of snapshots
        self.persist_path = persist_path
        self.auto_persist = auto_persist

        # Load from disk if path exists
        if persist_path and persist_path.exists():
            self._load_from_disk()

    def save_state(self, state: LoopState) -> None:
        """
        Save loop state.

        Args:
            state: State to save
        """
        state.updated_at = datetime.now()
        self._states[state.loop_id] = state

        if self.auto_persist and self.persist_path:
            self._persist_to_disk()

        logger.debug(f"Saved state for loop {state.loop_id}")

    def load_state(self, loop_id: str) -> LoopState | None:
        """
        Load loop state by ID.

        Args:
            loop_id: ID of the loop to load

        Returns:
            LoopState if found, None otherwise
        """
        return self._states.get(loop_id)

    def list_loops(self) -> list[str]:
        """
        List all loop IDs.

        Returns:
            List of loop IDs
        """
        return list(self._states.keys())

    def delete_state(self, loop_id: str) -> bool:
        """
        Delete loop state.

        Args:
            loop_id: ID of the loop to delete

        Returns:
            True if deleted, False if not found
        """
        if loop_id in self._states:
            del self._states[loop_id]
            if loop_id in self._snapshots:
                del self._snapshots[loop_id]

            if self.auto_persist and self.persist_path:
                self._persist_to_disk()

            logger.info(f"Deleted state for loop {loop_id}")
            return True

        return False

    def create_snapshot(self, loop_id: str) -> str | None:
        """
        Create a snapshot of the current loop state.

        Args:
            loop_id: ID of the loop to snapshot

        Returns:
            Snapshot ID if successful, None if loop not found
        """
        state = self._states.get(loop_id)
        if not state:
            return None

        snapshot_id = f"{loop_id}_{datetime.now().isoformat()}"
        snapshot_data = self._state_to_dict(state)

        if loop_id not in self._snapshots:
            self._snapshots[loop_id] = []

        self._snapshots[loop_id].append({
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "data": snapshot_data,
        })

        logger.info(f"Created snapshot {snapshot_id}")
        return snapshot_id

    def list_snapshots(self, loop_id: str) -> list[dict]:
        """
        List snapshots for a loop.

        Args:
            loop_id: ID of the loop

        Returns:
            List of snapshot metadata (id, timestamp)
        """
        snapshots = self._snapshots.get(loop_id, [])
        return [
            {"snapshot_id": s["snapshot_id"], "timestamp": s["timestamp"]}
            for s in snapshots
        ]

    def restore_snapshot(self, loop_id: str, snapshot_id: str) -> bool:
        """
        Restore a loop state from a snapshot.

        Args:
            loop_id: ID of the loop
            snapshot_id: ID of the snapshot to restore

        Returns:
            True if restored, False if snapshot not found
        """
        snapshots = self._snapshots.get(loop_id, [])

        for snapshot in snapshots:
            if snapshot["snapshot_id"] == snapshot_id:
                state = self._dict_to_state(snapshot["data"])
                self._states[loop_id] = state
                logger.info(f"Restored snapshot {snapshot_id}")
                return True

        return False

    def get_branch(self, loop_id: str, branch_id: str) -> Branch | None:
        """
        Get a specific branch from a loop.

        Args:
            loop_id: ID of the loop
            branch_id: ID of the branch

        Returns:
            Branch if found, None otherwise
        """
        state = self._states.get(loop_id)
        if state:
            return state.branches.get(branch_id)
        return None

    def update_branch(self, loop_id: str, branch: Branch) -> bool:
        """
        Update a branch in a loop.

        Args:
            loop_id: ID of the loop
            branch: Updated branch

        Returns:
            True if updated, False if loop not found
        """
        state = self._states.get(loop_id)
        if not state:
            return False

        state.branches[branch.id] = branch
        state.updated_at = datetime.now()

        if self.auto_persist and self.persist_path:
            self._persist_to_disk()

        return True

    def _state_to_dict(self, state: LoopState) -> dict:
        """Convert state to serializable dict."""
        # This is a simplified serialization
        # In production, you'd want proper serialization for all nested objects
        return {
            "loop_id": state.loop_id,
            "loop_number": state.loop_number,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "branch_ids": list(state.branches.keys()),
            "total_papers": state.total_papers,
            "total_summaries": state.total_summaries,
            "hypothesis_count": len(state.hypotheses),
        }

    def _dict_to_state(self, data: dict) -> LoopState:
        """Convert dict back to state (stub - would need full deserialization)."""
        from .models import LoopState
        # This is a stub - full implementation would deserialize all nested objects
        return LoopState(
            loop_id=data["loop_id"],
            loop_number=data["loop_number"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def _persist_to_disk(self) -> None:
        """Persist all states to disk."""
        if not self.persist_path:
            return

        try:
            data = {
                "states": {
                    loop_id: self._state_to_dict(state)
                    for loop_id, state in self._states.items()
                },
                "snapshots": self._snapshots,
            }

            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Persisted state to {self.persist_path}")

        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _load_from_disk(self) -> None:
        """Load states from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            # Note: This only loads metadata, not full state
            # Full implementation would deserialize completely
            self._snapshots = data.get("snapshots", {})
            logger.info(f"Loaded state metadata from {self.persist_path}")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def get_stats(self) -> dict:
        """Get overall statistics."""
        total_papers = 0
        total_summaries = 0
        total_branches = 0

        for state in self._states.values():
            total_papers += state.total_papers
            total_summaries += state.total_summaries
            total_branches += len(state.branches)

        return {
            "total_loops": len(self._states),
            "total_branches": total_branches,
            "total_papers": total_papers,
            "total_summaries": total_summaries,
            "total_snapshots": sum(len(s) for s in self._snapshots.values()),
        }
