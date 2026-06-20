import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

// --- CONFIGURATION ---
const TIME_BUCKETS = 256;
const PRICE_BUCKETS = 128;
const HEIGHT_SCALE = 15.0;

class LOBVisualizer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.width = this.container.clientWidth;
        this.height = this.container.clientHeight;

        try {
            this.initScene();
            this.initDataTexture();
            this.initTerrain();
            this.initPostProcessing();

            // Start Render Loop
            this.clock = new THREE.Clock();
            this.animate();
            
            // Mock incoming websocket data for the 3D demo
            setInterval(() => this.mockIncomingTick(), 100);
        } catch (e) {
            this.container.innerHTML = `<div style="color: red; padding: 20px;">WebGL Error: ${e.message}</div>`;
        }
    }

    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color('#0A0E17');
        this.scene.fog = new THREE.FogExp2('#0A0E17', 0.015);

        this.camera = new THREE.PerspectiveCamera(40, this.width / this.height, 0.1, 1000);
        this.camera.position.set(0, 40, 60);
        this.camera.lookAt(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
        this.renderer.setSize(this.width || 100, this.height || 100); // Fallback until ResizeObserver fires
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.domElement.style.width = '100%';
        this.renderer.domElement.style.height = '100%';
        this.renderer.domElement.style.display = 'block';
        this.container.appendChild(this.renderer.domElement);

        // Debug Grid to prove the scene is actually rendering
        const gridHelper = new THREE.GridHelper(100, 50, 0x00E5A0, 0x232936);
        gridHelper.position.y = -1;
        this.scene.add(gridHelper);

        const ro = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    this.width = width;
                    this.height = height;
                    this.camera.aspect = width / height;
                    this.camera.updateProjectionMatrix();
                    this.renderer.setSize(width, height);
                    if (this.composer) this.composer.setSize(width, height);
                }
            }
        });
        ro.observe(this.container);
    }

    initDataTexture() {
        // Pre-allocate the ring buffer: TIME_BUCKETS * PRICE_BUCKETS * 4 (RGBA)
        const size = TIME_BUCKETS * PRICE_BUCKETS;
        this.dataArray = new Uint8Array(size * 4); // Dell compatibility: Uint8 instead of Float32
        
        this.dataTexture = new THREE.DataTexture(this.dataArray, TIME_BUCKETS, PRICE_BUCKETS, THREE.RGBAFormat, THREE.UnsignedByteType);
        this.dataTexture.needsUpdate = true;
        this.currentIndex = 0; // Ring buffer pointer
    }

    initTerrain() {
        // 1. A single static PlaneGeometry. CPU never touches geometry again.
        const geometry = new THREE.PlaneGeometry(100, 50, TIME_BUCKETS - 1, PRICE_BUCKETS - 1);
        geometry.rotateX(-Math.PI / 2);

        // 2. The Custom ShaderMaterial
        const material = new THREE.ShaderMaterial({
            uniforms: {
                uHeightMap: { value: this.dataTexture },
                uHeightScale: { value: HEIGHT_SCALE },
                uTime: { value: 0.0 },
                uCurrentIndex: { value: 0.0 }
            },
            vertexShader: `
                uniform sampler2D uHeightMap;
                uniform float uHeightScale;
                uniform float uCurrentIndex;
                varying vec2 vUv;
                varying float vHeight;
                varying float vSide;

                void main() {
                    vUv = uv;
                    // Ring buffer UV wrapping
                    float wrappedU = mod(uv.x + uCurrentIndex, 1.0);
                    vec4 data = texture2D(uHeightMap, vec2(wrappedU, uv.y));
                    
                    vHeight = data.r; // Volume
                    vSide = data.g;   // 0 = Bid, 1 = Ask

                    vec3 pos = position;
                    pos.y += vHeight * uHeightScale;
                    
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
                }
            `,
            fragmentShader: `
                varying vec2 vUv;
                varying float vHeight;
                varying float vSide;

                void main() {
                    // Density and Glow math
                    float glow = pow(vHeight, 2.5); 

                    vec3 bidColor = vec3(0.0, 0.898, 0.627); // #00E5A0
                    vec3 askColor = vec3(1.0, 0.298, 0.380); // #FF4C61
                    
                    vec3 baseColor = mix(bidColor, askColor, vSide);
                    
                    // Core gets white hot on massive volume
                    vec3 finalColor = mix(baseColor * glow, vec3(1.0), pow(vHeight, 5.0));

                    gl_FragColor = vec4(finalColor, 1.0);
                }
            `,
            wireframe: false,
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false
        });

        this.terrain = new THREE.Mesh(geometry, material);
        this.terrain.frustumCulled = false;
        this.terrain.matrixAutoUpdate = false;
        this.terrain.updateMatrix();
        
        this.scene.add(this.terrain);
    }

    initPostProcessing() {
        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));

        const bloomPass = new UnrealBloomPass(new THREE.Vector2(this.width, this.height), 1.5, 0.4, 0.15);
        this.composer.addPass(bloomPass);
    }

    mockIncomingTick() {
        // Overwrite the oldest column in the ring buffer
        this.currentIndex = (this.currentIndex + 1) % TIME_BUCKETS;
        
        for (let p = 0; p < PRICE_BUCKETS; p++) {
            const index = (p * TIME_BUCKETS + this.currentIndex) * 4;
            
            // Generate some random liquidity walls
            const isBid = p < PRICE_BUCKETS / 2 ? 0.0 : 1.0;
            let volume = 0.0;
            
            // Create "walls" at specific price levels
            if (p === 30 || p === 90) volume = Math.random() * 0.9; 
            else if (Math.random() > 0.95) volume = Math.random() * 0.4;
            
            this.dataArray[index] = volume * 255; // R: Volume
            this.dataArray[index + 1] = isBid * 255; // G: Side
            this.dataArray[index + 2] = 0; // B
            this.dataArray[index + 3] = 255; // A
        }
        
        this.dataTexture.needsUpdate = true;
        this.terrain.material.uniforms.uCurrentIndex.value = this.currentIndex / TIME_BUCKETS;
    }

    onWindowResize() {
        this.width = this.container.clientWidth;
        this.height = this.container.clientHeight;
        this.camera.aspect = this.width / this.height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.width, this.height);
        this.composer.setSize(this.width, this.height);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        const elapsed = this.clock.getElapsedTime();
        this.terrain.material.uniforms.uTime.value = elapsed;
        
        // Slowly rotate camera to admire the matrix
        this.camera.position.x = Math.sin(elapsed * 0.1) * 60;
        this.camera.position.z = Math.cos(elapsed * 0.1) * 60;
        this.camera.lookAt(0, 0, 0);

        this.composer.render();
    }
}

// Instantiate immediately. ES modules run deferred by default, so DOM is ready.
new LOBVisualizer('chart-stub');
