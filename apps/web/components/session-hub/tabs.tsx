"use client";

export function HubTabs({
  id,
  label,
  tabs,
  value,
  onChange,
}: {
  id: string;
  label: string;
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="hub-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          id={`${id}-tab-${tab.id}`}
          role="tab"
          aria-selected={value === tab.id}
          aria-controls={`${id}-panel-${tab.id}`}
          tabIndex={value === tab.id ? 0 : -1}
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => {
            let next: number;
            if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
            else if (event.key === "ArrowLeft")
              next = (index + tabs.length - 1) % tabs.length;
            else if (event.key === "Home") next = 0;
            else if (event.key === "End") next = tabs.length - 1;
            else return;
            event.preventDefault();
            onChange(tabs[next].id);
            document.getElementById(`${id}-tab-${tabs[next].id}`)?.focus();
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
