import Link from "next/link";

interface AppHeaderProps {
  eyebrow?: string;
  title?: string;
  description?: string;
  actions?: React.ReactNode;
}

export function AppHeader({
  eyebrow = "Research mission control",
  title = "Indra",
  description,
  actions,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link className="brand-lockup" href="/projects" aria-label="Indra projects">
          <span className="brand-mark" aria-hidden="true">I</span>
          <span>
            <span className="brand-name">Indra</span>
            <span className="brand-caption">Evidence-backed research navigation</span>
          </span>
        </Link>
        <nav className="primary-nav" aria-label="Primary navigation">
          <Link href="/projects">Projects</Link>
          <span className="nav-disabled" title="Available in a later roadmap phase">Research maps</span>
          <span className="nav-disabled" title="Available in a later roadmap phase">Exports</span>
        </nav>
      </div>
      {(title || description || actions) && (
        <div className="page-heading">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            {description ? <p className="page-description">{description}</p> : null}
          </div>
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
      )}
    </header>
  );
}
