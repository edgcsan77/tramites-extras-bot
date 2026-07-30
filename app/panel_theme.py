import html


def esc(value) -> str:
    return html.escape(
        str(
            value
            if value is not None
            else ""
        ),
        quote=True,
    )


def panel_css() -> str:
    return """
    :root {
      --bg: #f4f6f8;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #e5e7eb;

      --primary: #334155;
      --primary-dark: #1e293b;

      --success: #166534;
      --success-soft: #dcfce7;

      --warning: #a16207;
      --warning-soft: #fef3c7;

      --danger: #991b1b;
      --danger-soft: #fee2e2;

      --info: #1d4ed8;
      --info-soft: #dbeafe;

      --shadow:
        0 8px 24px
        rgba(15, 23, 42, 0.07);

      --radius: 18px;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family:
        Arial,
        Helvetica,
        sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .wrap {
      max-width: 1500px;
      margin: 0 auto;
      padding: 16px;
    }

    .hero {
      background:
        linear-gradient(
          135deg,
          #1f2937 0%,
          #334155 55%,
          #475569 100%
        );

      color: #ffffff;
      border-radius: 24px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: var(--shadow);
    }

    .hero-row,
    .hero-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }

    .hero h1 {
      margin: 0 0 8px;
      font-size: 1.9rem;
    }

    .hero-sub,
    .subtitle {
      color:
        rgba(
          255,
          255,
          255,
          0.86
        );

      line-height: 1.5;
    }

    .toolbar,
    .nav {
      display: flex;
      gap: 9px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 16px;
    }

    .cards,
    .grid {
      display: grid;
      grid-template-columns:
        repeat(
          5,
          minmax(0, 1fr)
        );

      gap: 12px;
      margin-bottom: 18px;
    }

    .card,
    .stat {
      position: relative;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .card::before,
    .stat::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: #cbd5e1;
    }

    .card.success::before,
    .stat.success::before {
      background: var(--success);
    }

    .card.warning::before,
    .stat.warning::before {
      background: var(--warning);
    }

    .card.danger::before,
    .stat.danger::before {
      background: var(--danger);
    }

    .card.info::before,
    .stat.info::before {
      background: var(--info);
    }

    .label,
    .stat .label {
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      margin-bottom: 8px;
    }

    .value,
    .stat strong {
      display: block;
      font-size: 1.7rem;
      line-height: 1.1;
      font-weight: 900;
    }

    .box {
      background: var(--card);
      border: 1px solid #eef2f7;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      margin-bottom: 18px;
    }

    .head {
      padding: 16px 18px;
      border-bottom:
        1px solid
        var(--line);

      background: #fafbfc;

      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .head h2,
    .head h3,
    .head strong {
      margin: 0;
    }

    .content {
      padding: 16px 18px;
    }

    .filters,
    .form-grid {
      display: grid;
      grid-template-columns:
        repeat(
          4,
          minmax(0, 1fr)
        );

      gap: 10px;
      align-items: end;
    }

    .form-grid.cols-3 {
      grid-template-columns:
        repeat(
          3,
          minmax(0, 1fr)
        );
    }

    .form-grid.cols-5 {
      grid-template-columns:
        repeat(
          5,
          minmax(0, 1fr)
        );
    }

    .field label {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 800;
      margin-bottom: 6px;
    }

    input,
    select,
    textarea {
      width: 100%;
      border:
        1px solid
        #d1d5db;

      border-radius: 12px;
      padding: 11px 12px;
      background: #ffffff;
      color: var(--text);
      font: inherit;
      outline: none;
    }

    textarea {
      min-height: 110px;
      resize: vertical;
    }

    input:focus,
    select:focus,
    textarea:focus {
      border-color:
        var(--primary);

      box-shadow:
        0 0 0 3px
        rgba(
          51,
          65,
          85,
          0.10
        );
    }

    .btn {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      gap: 6px;

      min-height: 39px;
      border: 0;
      border-radius: 11px;
      padding: 9px 13px;

      background: var(--primary);
      color: #ffffff;

      text-decoration: none;
      font-weight: 800;
      cursor: pointer;
      white-space: nowrap;
    }

    .btn:hover {
      opacity: 0.90;
    }

    .btn-primary {
      background: var(--primary);
    }

    .btn-success,
    .btn-green {
      background: var(--success);
    }

    .btn-warning {
      background: var(--warning);
    }

    .btn-danger,
    .btn-red {
      background: #b91c1c;
    }

    .btn-info {
      background: var(--info);
    }

    .btn-light,
    .btn.light {
      background: #ffffff;
      color: #0f172a;
    }

    .btn-soft {
      background: #e2e8f0;
      color: #1e293b;
    }

    .btn-sm {
      min-height: 32px;
      padding: 6px 9px;
      font-size: 0.80rem;
    }

    .inline-form {
      display: inline-flex;
      gap: 7px;
      align-items: center;
      flex-wrap: wrap;
      margin: 2px;
    }

    .inline-form input {
      width: 92px;
      min-width: 92px;
    }

    .actions {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      align-items: center;
    }

    .table-wrap {
      width: 100%;
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 850px;
    }

    th {
      background: #111827;
      color: #ffffff;
      text-align: left;
      padding: 12px;
      white-space: nowrap;
      font-size: 0.85rem;
    }

    td {
      padding: 11px 12px;
      border-bottom:
        1px solid
        var(--line);

      vertical-align: top;
    }

    tbody tr:hover {
      background: #f8fafc;
    }

    code,
    .mono {
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        Consolas,
        monospace;

      font-size: 0.82rem;
      word-break: break-all;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 0.74rem;
      font-weight: 900;
      white-space: nowrap;
    }

    .badge-success,
    .badge.ok {
      background: var(--success-soft);
      color: var(--success);
    }

    .badge-warning,
    .badge.warn {
      background: var(--warning-soft);
      color: #92400e;
    }

    .badge-danger,
    .badge.bad {
      background: var(--danger-soft);
      color: var(--danger);
    }

    .badge-info,
    .badge.info {
      background: var(--info-soft);
      color: var(--info);
    }

    .badge-muted,
    .badge.muted {
      background: #e5e7eb;
      color: #475569;
    }

    .small {
      color: var(--muted);
      font-size: 0.80rem;
      line-height: 1.45;
    }

    .muted {
      color: var(--muted);
    }

    .two {
      display: grid;
      grid-template-columns:
        repeat(
          2,
          minmax(0, 1fr)
        );

      gap: 18px;
    }

    .qr-box {
      max-width: 530px;
      margin: 0 auto;
      text-align: center;
    }

    .qr-box img {
      display: block;
      width: 100%;
      max-width: 420px;
      margin: 0 auto;
      border-radius: 16px;
      background: #ffffff;
      padding: 12px;
      border: 1px solid var(--line);
    }

    .empty {
      padding: 24px;
      text-align: center;
      color: var(--muted);
    }

    @media (
      max-width: 1100px
    ) {
      .cards,
      .grid {
        grid-template-columns:
          repeat(
            2,
            minmax(0, 1fr)
          );
      }

      .filters,
      .form-grid,
      .form-grid.cols-3,
      .form-grid.cols-5 {
        grid-template-columns:
          repeat(
            2,
            minmax(0, 1fr)
          );
      }

      .two {
        grid-template-columns: 1fr;
      }
    }

    @media (
      max-width: 640px
    ) {
      .wrap {
        padding: 10px;
      }

      .hero {
        border-radius: 17px;
        padding: 17px;
      }

      .hero h1 {
        font-size: 1.55rem;
      }

      .cards,
      .grid,
      .filters,
      .form-grid,
      .form-grid.cols-3,
      .form-grid.cols-5 {
        grid-template-columns: 1fr;
      }

      .btn {
        width: 100%;
      }

      .inline-form {
        display: flex;
        width: 100%;
      }

      .inline-form input {
        flex: 1;
        width: auto;
      }
    }

    .section {
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      margin-bottom: 16px;
      overflow: hidden;
      box-shadow:
        0 6px 20px
        rgba(15, 23, 42, 0.06);
    }
    
    .collapsible-head {
      cursor: pointer;
      user-select: none;
    }
    
    .collapsible-head:hover {
      background: #f3f4f6;
    }
    
    .collapse-icon {
      display: inline-block;
      transition: transform 0.18s ease;
      margin-right: 6px;
    }
    
    .collapsible-head.closed
    .collapse-icon {
      transform: rotate(-90deg);
    }
    
    .collapsible-body.open {
      display: block;
    }
    
    .collapsible-body.closed {
      display: none;
    }
    
    .grid-hero {
      display: grid;
      grid-template-columns:
        repeat(
          4,
          minmax(0, 1fr)
        );
      gap: 12px;
      margin-top: 18px;
    }
    
    .glass {
      background:
        rgba(
          255,
          255,
          255,
          0.12
        );
      border:
        1px solid
        rgba(
          255,
          255,
          255,
          0.18
        );
      border-radius: 16px;
      padding: 14px;
      backdrop-filter: blur(6px);
    }
    
    .glass .label {
      color:
        rgba(
          255,
          255,
          255,
          0.75
        );
    }
    
    .glass .value {
      color: #ffffff;
    }
    
    .wallet-grid {
      display: grid;
      grid-template-columns:
        repeat(
          2,
          minmax(0, 1fr)
        );
      gap: 12px;
    }
    
    .wallet {
      border:
        1px solid
        #e5e7eb;
      border-radius: 14px;
      padding: 14px;
      background: #f8fafc;
    }
    
    .wallet-title {
      font-weight: 900;
      margin-bottom: 9px;
    }
    
    .wallet-values {
      display: grid;
      grid-template-columns:
        repeat(
          3,
          minmax(0, 1fr)
        );
      gap: 8px;
    }
    
    .wallet-number {
      background: #ffffff;
      border:
        1px solid
        #e5e7eb;
      border-radius: 10px;
      padding: 9px;
    }
    
    .wallet-number span {
      display: block;
      color: #6b7280;
      font-size: 0.72rem;
      font-weight: 800;
    }
    
    .wallet-number strong {
      display: block;
      margin-top: 4px;
      font-size: 1.15rem;
    }
    
    .status-dot {
      display: inline-block;
      width: 9px;
      height: 9px;
      border-radius: 999px;
      margin-right: 5px;
    }
    
    .status-dot.on {
      background: #16a34a;
    }
    
    .status-dot.off {
      background: #dc2626;
    }
    
    .btn-row {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      align-items: center;
    }
    
    .notice {
      border-radius: 12px;
      padding: 11px 13px;
      margin-bottom: 12px;
      background: #eff6ff;
      color: #1e40af;
      border: 1px solid #bfdbfe;
    }
    
    @media (max-width: 900px) {
      .grid-hero,
      .wallet-grid {
        grid-template-columns:
          repeat(
            2,
            minmax(0, 1fr)
          );
      }
    }
    
    @media (max-width: 640px) {
      .grid-hero,
      .wallet-grid,
      .wallet-values {
        grid-template-columns: 1fr;
      }
    }
    """


def badge_html(
    text: str,
    kind: str = "muted",
) -> str:
    safe_kind = (
        kind
        if kind in {
            "success",
            "warning",
            "danger",
            "info",
            "muted",
        }
        else "muted"
    )

    return (
        f'<span class="badge '
        f'badge-{safe_kind}">'
        f'{esc(text)}'
        f'</span>'
    )


def page_html(
    *,
    title: str,
    hero_title: str,
    hero_subtitle: str = "",
    hero_actions: str = "",
    body: str,
) -> str:
    return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">

      <meta
        name="viewport"
        content="width=device-width,initial-scale=1"
      >

      <title>{esc(title)}</title>

      <style>
        {panel_css()}
      </style>
    </head>

    <body>
      <div class="wrap">
        <section class="hero">
          <div class="hero-row">
            <div>
              <h1>{esc(hero_title)}</h1>

              {
                f'<div class="hero-sub">'
                f'{esc(hero_subtitle)}'
                f'</div>'
                if hero_subtitle
                else ''
              }
            </div>

            <div class="actions">
              {hero_actions}
            </div>
          </div>
        </section>

        {body}
      </div>

      <script>
        function toggleSection(bodyId, head) {{
          const body =
            document.getElementById(bodyId);

          if (!body) {{
            return;
          }}

          const isOpen =
            body.classList.contains("open");

          body.classList.toggle(
            "open",
            !isOpen
          );

          body.classList.toggle(
            "closed",
            isOpen
          );

          if (head) {{
            head.classList.toggle(
              "open",
              !isOpen
            );

            head.classList.toggle(
              "closed",
              isOpen
            );
          }}
        }}
      </script>
    </body>
    </html>
    """
