use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use std::fs;
use wasmtime::*;
use wasmtime_wasi::WasiCtxBuilder;
use wasi_common::pipe::{ReadPipe, WritePipe};

#[pyclass]
struct WasmRunner {
    engine: Engine,
    module: Module,
    linker: Linker<wasmtime_wasi::WasiCtx>,
}

#[pymethods]
impl WasmRunner {
    #[new]
    fn new(filename: String) -> PyResult<Self> {
        let wasm_bytes = fs::read(&filename)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to read file: {}", e)))?;
        
        // Create engine and module
        let engine = Engine::default();
        let module = Module::from_binary(&engine, &wasm_bytes)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to load WASM module: {}", e)))?;

        // Create linker with WASI
        let mut linker = Linker::new(&engine);
        wasmtime_wasi::add_to_linker(&mut linker, |s| s)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to setup WASI: {}", e)))?;

        Ok(WasmRunner { engine, module, linker })
    }

    fn __call__(&mut self, input: String) -> PyResult<String> {
        self.run_wasm(input)
            .map_err(|e| PyRuntimeError::new_err(format!("WASM execution failed: {}", e)))
    }
}

impl WasmRunner {
    fn run_wasm(&mut self, input: String) -> anyhow::Result<String> {
        // Setup stdin/stdout pipes
        let stdin = ReadPipe::from(input);
        let stdout = WritePipe::new_in_memory();
        let stdout_clone = stdout.clone();

        // Build WASI context
        let wasi = WasiCtxBuilder::new()
            .stdin(Box::new(stdin))
            .stdout(Box::new(stdout))
            .build();

        // Create store with WASI context
        let mut store = Store::new(&self.engine, wasi);

        // Instantiate and run
        self.linker.module(&mut store, "", &self.module)?;
        self.linker
            .get_default(&mut store, "")?
            .typed::<(), ()>(&store)?
            .call(&mut store, ())?;

        // Get output
        drop(store);
        let contents = stdout_clone
            .try_into_inner()
            .map_err(|_| anyhow::anyhow!("stdout still in use"))?
            .into_inner();
        
        Ok(String::from_utf8(contents)?)
    }
}

#[pymodule]
fn wasm_runner(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<WasmRunner>()?;
    Ok(())
}
