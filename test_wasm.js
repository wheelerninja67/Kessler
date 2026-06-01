const fs = require('fs');
const buffer = fs.readFileSync('dashboard/public/kessler.wasm');

const imports = {
  env: {
    memory: new WebAssembly.Memory({ initial: 256 }),
    __assert_fail: () => { console.error("Assert failed"); }
  }
};

WebAssembly.instantiate(buffer, imports).then(result => {
  const exports = result.instance.exports;
  console.log("WASM loaded. Init function:", !!exports.init_simulation);
  const success = exports.init_simulation(10000, 42n);
  console.log("Init result:", success);
}).catch(err => {
  console.error("WASM Instantiation Error:", err.message);
});
