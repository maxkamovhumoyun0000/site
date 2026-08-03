const fs = require('fs');
const file = '/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/GlobalVoiceRoomContext.tsx';
let code = fs.readFileSync(file, 'utf8');

// Fix startMedia
code = code.replace(
  /const isAndroid = typeof navigator !== "undefined" && \/android\/i\.test\(navigator\.userAgent\);\s*const audioConstraints = isAndroid \? \{ echoCancellation: false, noiseSuppression: true, autoGainControl: true \} : true;\s*const stream = await navigator\.mediaDevices\.getUserMedia\(\{ audio: audioConstraints \}\);/,
  `const isAndroid = typeof navigator !== "undefined" && /android/i.test(navigator.userAgent);
      // echoCancellation: false forces Android to stay in Media Volume mode instead of Call Volume
      const audioConstraints = isAndroid ? { echoCancellation: false } : true;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });`
);

// Fix pc.ontrack
code = code.replace(/pc\.ontrack = \(event\) => \{[\s\S]*?if \(mixDestinationRef\.current\) \{\s*analyser\.connect\(mixDestinationRef\.current\);\s*\}\s*\} catch \(e\) \{\s*console\.warn\("Could not create analyser for remote stream", e\);\s*\}\s*\};/,
`pc.ontrack = (event) => {
      let audio = audioElementsRef.current.get(peerId);
      if (!audio) {
        audio = document.createElement("audio");
        audio.autoplay = true;
        audio.playsInline = true;
        audio.style.display = "none";
        document.body.appendChild(audio);
        audioElementsRef.current.set(peerId, audio);
      }
      
      audio.srcObject = event.streams[0];
      audio.muted = false;
      
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch(e => {
           console.error("Audio autoplay failed:", e);
           // Fallback: Try to play on first user interaction if blocked
           const resumeAudio = () => {
             audio?.play().catch(console.error);
             document.removeEventListener('click', resumeAudio);
             document.removeEventListener('touchstart', resumeAudio);
           };
           document.addEventListener('click', resumeAudio);
           document.addEventListener('touchstart', resumeAudio);
        });
      }

      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(console.error);
      }

      try {
        const stream = event.streams[0];
        const source = audioContextRef.current.createMediaStreamSource(stream);
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analysersRef.current.set(peerId, analyser);
        
        if (mixDestinationRef.current) {
          analyser.connect(mixDestinationRef.current);
        }
      } catch (e) {
        console.warn("Could not create analyser for remote stream", e);
      }
    };`
);

fs.writeFileSync(file, code);
