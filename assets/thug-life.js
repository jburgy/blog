import 'https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js';

// main.js
const video = document.getElementById('webcam');
const canvas = document.getElementById('sunglasses-canvas');
const btn = document.getElementById('drop-btn');

function startWebcam() {
  navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    .then((stream) => {
      video.srcObject = stream;
      video.addEventListener('loadedmetadata', () => {
        // Match canvas size to video size
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.style.width = `${video.offsetWidth}px`;
        canvas.style.height = `${video.offsetHeight}px`;
      });
    })
    .catch((err) => {
      video.poster = '';
      video.alt = 'Webcam not available';
      alert(`Could not access webcam: ${err.message}`);
    });
}

startWebcam();

// Load face-api.js models
async function loadFaceApiModels() {
  const modelUrl = 'https://justadudewhohacks.github.io/face-api.js/models';
  await faceapi.nets.tinyFaceDetector.loadFromUri(modelUrl);
  await faceapi.nets.faceLandmark68TinyNet.loadFromUri(modelUrl);
}

// Bad Guy meme sunglasses pixel art with bridge and shine
// 0: transparent, 1: black, 2: white (shine)
const sunglassesPixels = [
  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
  [1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1],
  [0, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1, 0],
  [0, 0, 1, 1, 2, 1, 2, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 2, 1, 2, 1, 1, 1, 1, 0, 0],
  [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
];

function drawSunglasses(ctx, x, y, scale = 10) {
  sunglassesPixels.forEach((rowArr, row) => {
    rowArr.forEach((val, col) => {
      if (val === 0) return;
      ctx.fillStyle = val === 1 ? '#111' : '#fff';
      ctx.fillRect(x + col * scale, y + row * scale, scale, scale);
    });
  });
}

function drawTrackedSunglasses(nose) {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!nose) return;
  // Place sunglasses above nose tip
  const scale = Math.max(8, Math.floor(canvas.width / 80));
  const sw = sunglassesPixels[0].length * scale;
  const sh = sunglassesPixels.length * scale;
  const x = nose.x - sw / 2;
  const y = nose.y - sh / 2;
  drawSunglasses(ctx, x, y, scale);
}

async function trackFace() {
  if (!video.srcObject) return;
  const options = new faceapi.TinyFaceDetectorOptions();
  const result = await faceapi.detectSingleFace(video, options).withFaceLandmarks(true);
  if (result && result.landmarks) {
    // Nose tip is landmark 30
    drawTrackedSunglasses(result.landmarks.positions[30]);
  }
  requestAnimationFrame(trackFace);
}

btn.addEventListener('click', async () => {
  if (!faceapi.nets.tinyFaceDetector.params) {
    await loadFaceApiModels();
  }
  trackFace();
});

function animateDrop() {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // Estimate nose position: center horizontally, 2/3 down vertically
  const scale = Math.max(8, Math.floor(canvas.width / 80));
  const sw = sunglassesPixels[0].length * scale;
  const sh = sunglassesPixels.length * scale;
  const targetX = Math.floor(canvas.width / 2 - sw / 2);
  const targetY = Math.floor(canvas.height * 0.62);
  const y = -sh;
  const dropFrames = 30;
  let frame = 0;

  function step() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // Ease out animation
    const progress = frame / dropFrames;
    const currentY = y + (targetY - y) * (1 - (1 - progress) ** 2);
    drawSunglasses(ctx, targetX, currentY, scale);
    frame++;
    if (frame <= dropFrames) {
      requestAnimationFrame(step);
    } else {
      drawSunglasses(ctx, targetX, targetY, scale);
    }
  }
  step();
}

btn.addEventListener('click', animateDrop);
