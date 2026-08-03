const fs = require('fs');
const files = [
  '/home/jus1-bea1s/Desktop/diamond site/app/student/test-views.tsx',
  '/home/jus1-bea1s/Desktop/diamond site/app/student/proctoring.tsx'
];

for (const file of files) {
  let content = fs.readFileSync(file, 'utf-8');
  content = content.replace(/bg-slate-700/g, 'bg-navy-800');
  content = content.replace(/border-slate-200/g, 'border-line');
  content = content.replace(/border-slate-600/g, 'border-white/10');
  content = content.replace(/text-slate-700/g, 'text-ink-700');
  content = content.replace(/bg-slate-100/g, 'bg-surface-soft');
  content = content.replace(/bg-slate-200/g, 'bg-line');
  
  content = content.replace(/group-hover:text-blue-600 dark:group-hover:text-blue-400/g, 'group-hover:text-cyan-600 dark:group-hover:text-cyan-400');
  content = content.replace(/group-hover:text-indigo-600 dark:group-hover:text-indigo-400/g, 'group-hover:text-cyan-600 dark:group-hover:text-cyan-400');
  content = content.replace(/hover:bg-indigo-50/g, 'hover:bg-cyan-50');
  
  fs.writeFileSync(file, content);
}
console.log("Migration complete 2.");
