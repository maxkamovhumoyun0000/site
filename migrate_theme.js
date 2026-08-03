const fs = require('fs');
const files = [
  '/home/jus1-bea1s/Desktop/diamond site/app/student/test-views.tsx',
  '/home/jus1-bea1s/Desktop/diamond site/app/student/proctoring.tsx'
];

for (const file of files) {
  let content = fs.readFileSync(file, 'utf-8');
  
  // Layouts
  content = content.replace(/bg-slate-50 dark:bg-slate-900/g, 'bg-background selection:bg-cyan-500/30 selection:text-cyan-900 dark:selection:text-cyan-100');
  
  // Cards
  content = content.replace(/bg-white dark:bg-slate-900 rounded-3xl/g, 'bg-white dark:bg-navy-900/50 rounded-[2rem]');
  content = content.replace(/shadow-xl border border-slate-200 dark:border-slate-800/g, 'shadow-premium border border-line dark:border-white/10');
  content = content.replace(/shadow-xl border-t-8 border-x border-b border-slate-200 dark:border-slate-800/g, 'shadow-premium border border-line dark:border-white/10');
  content = content.replace(/panel-card/g, 'bg-white dark:bg-navy-900/50 rounded-[2rem] shadow-premium border border-line dark:border-white/10 p-6 md:p-8');
  
  // Inner Cards / Elements
  content = content.replace(/bg-slate-50 dark:bg-slate-800\/50/g, 'bg-surface-soft dark:bg-white/5');
  content = content.replace(/border-slate-200 dark:border-slate-700\/50/g, 'border-line dark:border-white/10');
  content = content.replace(/border-slate-200 dark:border-slate-700/g, 'border-line dark:border-white/10');
  content = content.replace(/bg-slate-100 dark:bg-slate-800/g, 'bg-surface-soft dark:bg-white/5 border border-line dark:border-white/10');
  content = content.replace(/bg-slate-200 dark:bg-slate-800/g, 'bg-line dark:bg-white/10');
  content = content.replace(/border border-slate-100 dark:border-slate-700\/50/g, 'border border-line dark:border-white/10');
  
  // Text
  content = content.replace(/text-slate-800 dark:text-white/g, 'text-navy-900 dark:text-white');
  content = content.replace(/text-slate-800 dark:text-slate-200/g, 'text-navy-900 dark:text-white');
  content = content.replace(/text-slate-700 dark:text-slate-300/g, 'text-ink-700 dark:text-navy-200');
  content = content.replace(/text-slate-600 dark:text-slate-400/g, 'text-ink-600 dark:text-navy-300');
  content = content.replace(/text-slate-500 dark:text-slate-400/g, 'text-ink-500 dark:text-navy-300');
  content = content.replace(/text-slate-500/g, 'text-ink-500');
  content = content.replace(/text-slate-600/g, 'text-ink-600');
  
  // Interactive Buttons / Options
  content = content.replace(/bg-slate-50 hover:bg-blue-50 dark:bg-slate-800\/50 dark:hover:bg-slate-800/g, 'bg-surface-soft hover:bg-cyan-50 dark:bg-white/5 dark:hover:bg-cyan-500/10 hover:shadow-premium hover:-translate-y-1 transition-all');
  content = content.replace(/bg-slate-50 hover:bg-indigo-50 dark:bg-slate-800\/50 dark:hover:bg-slate-800/g, 'bg-surface-soft hover:bg-cyan-50 dark:bg-white/5 dark:hover:bg-cyan-500/10 hover:shadow-premium hover:-translate-y-1 transition-all');
  content = content.replace(/hover:border-blue-500 focus:outline-none focus:border-blue-500/g, 'hover:border-cyan-300 focus:outline-none focus:border-cyan-500 dark:hover:border-cyan-500/50');
  content = content.replace(/hover:border-indigo-500 focus:outline-none focus:border-indigo-500/g, 'hover:border-cyan-300 focus:outline-none focus:border-cyan-500 dark:hover:border-cyan-500/50');
  
  content = content.replace(/bg-blue-600 hover:bg-blue-700 text-white/g, 'bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600');
  content = content.replace(/bg-indigo-600 hover:bg-indigo-700 text-white/g, 'bg-navy-900 hover:bg-navy-800 text-white dark:bg-cyan-500 dark:hover:bg-cyan-600');
  content = content.replace(/bg-blue-500/g, 'bg-cyan-500');
  content = content.replace(/text-blue-600 dark:text-blue-400/g, 'text-cyan-600 dark:text-cyan-400');
  content = content.replace(/text-indigo-600 dark:text-indigo-400/g, 'text-cyan-600 dark:text-cyan-400');
  content = content.replace(/bg-blue-100 dark:bg-blue-500\/20/g, 'bg-cyan-50 dark:bg-cyan-500/10 border border-cyan-100 dark:border-cyan-500/20');
  content = content.replace(/bg-indigo-100 dark:bg-indigo-500\/20/g, 'bg-cyan-50 dark:bg-cyan-500/10 border border-cyan-100 dark:border-cyan-500/20');
  
  fs.writeFileSync(file, content);
}
console.log("Migration complete.");
