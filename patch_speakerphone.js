const fs = require('fs');
const file = '/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/GlobalVoiceRoomContext.tsx';
let code = fs.readFileSync(file, 'utf8');

// Add to context type
code = code.replace(
  /isRecording: boolean;\n  startRecording: \(\) => void;\n  stopRecordingAndUpload: \(homeworkId: string\) => Promise<void>;\n\}/,
  `isRecording: boolean;
  startRecording: () => void;
  stopRecordingAndUpload: (homeworkId: string) => Promise<void>;
  isSpeakerphone: boolean;
  toggleSpeakerphone: () => void;
}`
);

// Add to state
code = code.replace(
  /const \[isHiddenSpeaker, setIsHiddenSpeaker\] = useState\(false\);/,
  `const [isHiddenSpeaker, setIsHiddenSpeaker] = useState(false);
  const [isSpeakerphone, setIsSpeakerphone] = useState(true); // Default to true (boosted)`
);

// Add gainNodesRef
code = code.replace(
  /const analysersRef = useRef<Map<string, AnalyserNode>>\(new Map\(\)\);/,
  `const analysersRef = useRef<Map<string, AnalyserNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());`
);

// Add toggle function
code = code.replace(
  /const forceMutePeer = \(peerId: string\) => \{/,
  `const toggleSpeakerphone = () => {
    const newVal = !isSpeakerphone;
    setIsSpeakerphone(newVal);
    
    // Apply gain boost
    gainNodesRef.current.forEach(gainNode => {
       gainNode.gain.value = newVal ? 4.0 : 1.0;
    });
    
    // Apply sink ID if supported
    audioElementsRef.current.forEach(audio => {
       if (typeof (audio as any).setSinkId === "function") {
         navigator.mediaDevices.enumerateDevices().then(devices => {
           if (newVal) {
             const speaker = devices.find(d => d.kind === "audiooutput" && (d.label.toLowerCase().includes("speaker") || d.deviceId.toLowerCase().includes("speaker")));
             if (speaker) (audio as any).setSinkId(speaker.deviceId).catch(console.error);
             else (audio as any).setSinkId("default").catch(console.error);
           } else {
             const earpiece = devices.find(d => d.kind === "audiooutput" && d.label.toLowerCase().includes("earpiece"));
             if (earpiece) (audio as any).setSinkId(earpiece.deviceId).catch(console.error);
           }
         });
       }
    });
  };

  const forceMutePeer = (peerId: string) => {`
);

// Add gain node in ontrack
code = code.replace(
  /const source = audioContextRef\.current\.createMediaStreamSource\(stream\);\n\s*const analyser = audioContextRef\.current\.createAnalyser\(\);\n\s*analyser\.fftSize = 256;\n\s*source\.connect\(analyser\);\n\s*analysersRef\.current\.set\(peerId, analyser\);/,
  `const source = audioContextRef.current.createMediaStreamSource(stream);
        const gainNode = audioContextRef.current.createGain();
        gainNode.gain.value = isSpeakerphone ? 4.0 : 1.0;
        gainNodesRef.current.set(peerId, gainNode);
        source.connect(gainNode);
        
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        gainNode.connect(analyser);
        analysersRef.current.set(peerId, analyser);`
);

// Add isSpeakerphone and toggleSpeakerphone to Provider
code = code.replace(
  /isRecording, startRecording, stopRecordingAndUpload\n\s*\}\}\n\s*>/,
  `isRecording, startRecording, stopRecordingAndUpload,
        isSpeakerphone, toggleSpeakerphone
      }}
    >`
);

fs.writeFileSync(file, code);
