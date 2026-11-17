//! A header filter: on the request it reads `:path` and adds `x-epl-filter: 1`; on the
//! response it adds `x-epl-filter: 1`. No body access, no HTTP call, no logging. The same
//! job as the Lua header script, so the two runtimes price the same work.

use proxy_wasm::traits::{Context, HttpContext, RootContext};
use proxy_wasm::types::{Action, ContextType, LogLevel};

proxy_wasm::main! {{
    proxy_wasm::set_log_level(LogLevel::Warn);
    proxy_wasm::set_root_context(|_| -> Box<dyn RootContext> { Box::new(Root) });
}}

struct Root;

impl Context for Root {}

impl RootContext for Root {
    fn get_type(&self) -> Option<ContextType> {
        Some(ContextType::HttpContext)
    }

    fn create_http_context(&self, _context_id: u32) -> Option<Box<dyn HttpContext>> {
        Some(Box::new(Header))
    }
}

struct Header;

impl Context for Header {}

impl HttpContext for Header {
    fn on_http_request_headers(&mut self, _num_headers: usize, _end_of_stream: bool) -> Action {
        let _path = self.get_http_request_header(":path");
        self.add_http_request_header("x-epl-filter", "1");
        Action::Continue
    }

    fn on_http_response_headers(&mut self, _num_headers: usize, _end_of_stream: bool) -> Action {
        self.add_http_response_header("x-epl-filter", "1");
        Action::Continue
    }
}
