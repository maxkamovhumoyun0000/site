const fs = require('fs');

const FILE_PATH = '/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/role-video-detail.tsx';
let content = fs.readFileSync(FILE_PATH, 'utf8');

// Replace top container wrappers
content = content.replace(
  '<div className="flex-1 overflow-y-auto w-full p-0 sm:p-4 lg:p-8">\\n        <div className="max-w-5xl mx-auto space-y-6 relative">',
  '<div className="flex-1 overflow-y-auto w-full pt-4 sm:pt-6 pb-12">\\n        <div className="w-full max-w-[1800px] mx-auto flex flex-col lg:flex-row gap-8 sm:px-6 lg:px-8 2xl:px-12">\\n          {/* Main Player Area */}\\n          <div className="flex-1 relative">'
);

// Remove the `max-w-7xl` wrapper for `video ? (`
content = content.replace(
  '<div className="max-w-7xl mx-auto px-0 sm:px-6 lg:px-8">\\n              <div className="bg-black sm:rounded-2xl',
  '<div className="bg-black sm:rounded-2xl'
);

// Remove the end tags of the `max-w-7xl` wrapper
content = content.replace(
  /\\s*<\\/div>\\n          \\) : null\\}/,
  '\\n          ) : null}'
);

// Remove the {role} View badge
const roleBadgePattern = /\\s*<div className="flex items-center gap-2 mb-2">\\s*<div className="text-\\[10px\\].*?\\{role\\} View\\s*<\\/div>\\s*<\\/div>/s;
content = content.replace(roleBadgePattern, '');

// Add the empty sidebar before the closing tags
content = content.replace(
  '\\n        </div>\\n      </div>\\n    </main>',
  '\\n          {/* Sidebar Area for consistency */}\\n          <div className="w-full lg:w-[350px] xl:w-[400px] flex-shrink-0"></div>\\n        </div>\\n      </div>\\n    </main>'
);

fs.writeFileSync(FILE_PATH, content);
console.log("Updated role-video-detail.tsx layout.");
