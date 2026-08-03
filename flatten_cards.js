const fs = require('fs');

const files = [
  '/home/jus1-bea1s/Desktop/diamond site/app/student/test-views.tsx',
  '/home/jus1-bea1s/Desktop/diamond site/app/student/grammar/[topicId]/page.tsx'
];

for (const file of files) {
  if (fs.existsSync(file)) {
    let content = fs.readFileSync(file, 'utf-8');
    
    // Flatten nested backgrounds and borders
    content = content.replace(/bg-surface-soft dark:bg-white\/5 border border-line dark:border-white\/10/g, 'bg-transparent border border-line dark:border-white/5');
    content = content.replace(/bg-surface-soft dark:bg-white\/5/g, 'bg-transparent');
    // Remove shadow-inner from previously nested elements
    content = content.replace(/shadow-inner/g, '');
    
    // Clean up excessive nesting classes
    content = content.replace(/p-6 sm:p-10/g, 'p-4 sm:p-6');
    content = content.replace(/p-8 sm:p-12/g, 'p-4 sm:p-6');
    
    fs.writeFileSync(file, content);
  }
}
console.log("Card nesting flattened.");
