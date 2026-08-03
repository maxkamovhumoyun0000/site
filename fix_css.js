const fs = require('fs');
const file = '/home/jus1-bea1s/Desktop/diamond site/app/globals.css';
let content = fs.readFileSync(file, 'utf-8');

// The user asked to reduce font sizes where too large. In Tailwind, large fonts are often applied using utility classes in the TSX files,
// but if there are global heading styles, we can tone them down.
// Since Tailwind is used extensively, we should also check the actual TSX files for `text-3xl`, `text-4xl`, `text-5xl` etc.
// For now, let's add a global responsive rule override at the bottom of the CSS file if needed.
if (!content.includes('/* Mobile Font Overrides */')) {
  content += `

/* Mobile Font Overrides */
@media (max-width: 640px) {
  .text-4xl { font-size: 1.5rem !important; line-height: 2rem !important; }
  .text-5xl { font-size: 1.875rem !important; line-height: 2.25rem !important; }
  .text-6xl { font-size: 2.25rem !important; line-height: 2.5rem !important; }
  .text-7xl { font-size: 2.5rem !important; line-height: 2.75rem !important; }
  
  .p-8 { padding: 1.5rem !important; }
  .p-10 { padding: 1.5rem !important; }
  .p-12 { padding: 2rem !important; }
  
  .px-8 { padding-left: 1rem !important; padding-right: 1rem !important; }
  .py-8 { padding-top: 1.5rem !important; padding-bottom: 1.5rem !important; }
}
`;
}

fs.writeFileSync(file, content);
console.log("CSS updated.");
