const fs = require('fs');

function patchUI(file) {
  let code = fs.readFileSync(file, 'utf8');

  // Add isSpeakerphone and toggleSpeakerphone to context extraction
  code = code.replace(
    /toggleHiddenSpeaker,\n\s*isHiddenSpeaker,\n\s*isRecording,\n\s*startRecording,\n\s*stopRecordingAndUpload/,
    `toggleHiddenSpeaker,
    isHiddenSpeaker,
    isRecording,
    startRecording,
    stopRecordingAndUpload,
    isSpeakerphone,
    toggleSpeakerphone`
  );
  
  if (code.indexOf('isSpeakerphone') === -1) {
     // Moderator might have a different format
     code = code.replace(
       /toggleMute,\n\s*setErrorMsg,/,
       `toggleMute,
    setErrorMsg,
    isSpeakerphone,
    toggleSpeakerphone,`
     );
  }

  // Add the UI button next to the toggleMute button
  const buttonCode = `
                    <button onClick={toggleSpeakerphone} className={cx("w-7 h-7 shrink-0 rounded-full flex items-center justify-center transition-all ml-1", isSpeakerphone ? "bg-indigo-500/20 text-indigo-500 hover:bg-indigo-500 hover:text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white")} title={isSpeakerphone ? "Dinamik (Loudspeaker)" : "Quloqchin (Earpiece)"}>
                      {isSpeakerphone ? (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /></svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" /></svg>
                      )}
                    </button>`;

  code = code.replace(
    /(<button onClick=\{toggleMute\} className=\{cx\("w-7 h-7 shrink-0 rounded-full flex items-center justify-center transition-all", isMuted \? "bg-red-500\/20 text-red-500 hover:bg-red-500 hover:text-white" : "bg-emerald-500\/20 text-emerald-500 hover:bg-emerald-500 hover:text-white"\)\}>[\s\S]*?<\/button>)/,
    `$1${buttonCode}`
  );

  fs.writeFileSync(file, code);
}

patchUI('/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/student-voice-room.tsx');
patchUI('/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/moderator-voice-room.tsx');
