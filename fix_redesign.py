import re

with open('app/globals.css', 'r') as f:
    css = f.read()

mobile_css = """
  /* ====== MOBILE CARD TABLE FOR MODALS ====== */
  .mobile-card-table {
    border-collapse: separate;
    border-spacing: 0 12px;
    width: 100% !important;
    min-width: 0 !important;
  }
  .mobile-card-table thead {
    display: none !important;
  }
  .mobile-card-table tbody {
    display: block !important;
    width: 100% !important;
  }
  .mobile-card-table tr {
    display: flex !important;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 12px 14px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    margin-bottom: 8px;
  }
  [data-theme="dark"] .mobile-card-table tr {
    background: rgba(255, 255, 255, 0.03);
    border-color: rgba(255, 255, 255, 0.1);
  }
  .mobile-card-table td {
    display: block !important;
    width: auto !important;
    padding: 0 !important;
    border: none !important;
  }
  .mobile-card-table td:nth-child(1) {
    font-weight: bold;
    flex: 1 1 100%;
    margin-bottom: 4px;
  }
  .mobile-card-table td:last-child {
    flex: 1 1 100%;
    display: flex !important;
    justify-content: flex-end;
    margin-top: 4px;
  }
"""

if "MOBILE CARD TABLE FOR MODALS" not in css:
    css = css.replace('@media (max-width: 760px) {', '@media (max-width: 760px) {\n' + mobile_css, 1)

with open('app/globals.css', 'w') as f:
    f.write(css)

with open('app/page.tsx', 'r') as f:
    jsx = f.read()

# Apply to group roster
jsx = jsx.replace('<table className="w-full text-left border-collapse min-w-[480px]">', '<table className="w-full text-left border-collapse min-w-[480px] mobile-card-table">')

# Apply to temporary teacher picker
jsx = jsx.replace('<table className="min-w-[420px]">', '<table className="min-w-[420px] mobile-card-table">')

# Apply to substitutions list
jsx = jsx.replace('<table className="w-full text-left border-collapse min-w-[620px]">', '<table className="w-full text-left border-collapse min-w-[620px] mobile-card-table">')

# Modify teacher-arena-panel and overlay-modal-card in globals to behave like bottom sheet
bottom_sheet_css = """
  /* Bottom sheet behavior for teacher modal */
  .overlay-modal-card.admin-wide-modal {
    width: 100vw !important;
    max-width: 100vw !important;
    height: auto !important;
    max-height: calc(100dvh - 40px) !important;
    border-radius: 24px 24px 0 0 !important;
    margin-top: auto !important;
    border-bottom: none !important;
  }
  .overlay-modal-backdrop {
    align-items: flex-end !important;
    padding: 0 !important;
  }
"""
with open('app/globals.css', 'r') as f:
    css = f.read()

if "Bottom sheet behavior for teacher modal" not in css:
    css = css.replace('/* Modal card: full-width nearly full-height */\n  .overlay-modal-card.admin-wide-modal {', bottom_sheet_css + '\n  /* Modal card: full-width nearly full-height */\n  .overlay-modal-card.admin-wide-modal-old {')
    with open('app/globals.css', 'w') as f:
        f.write(css)

with open('app/page.tsx', 'w') as f:
    f.write(jsx)

print("Redesign applied")
