from typing import Dict, Any, Tuple
from contextlib import contextmanager
import os
import json

from wasmtime import Module, Store, Engine, Linker, WasiConfig
from wasmtime._instance import InstanceExports


class DslToSqlWasm:
    def __init__(self):
        self.engine = Engine()
        self.linker = Linker(self.engine)
        self.linker.define_wasi()
        self.store = Store(self.engine)
        self.store.set_wasi(self._get_wasi_config())
        self.module = Module.from_file(self.engine, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dsl_parser.wasm"))

    def _get_wasi_config(self) -> WasiConfig:
        wasi = WasiConfig()
        wasi.inherit_argv()
        wasi.inherit_env()
        wasi.inherit_stdout()
        wasi.inherit_stderr()
        wasi.inherit_stdin()
        return wasi

    @contextmanager
    def _gen_str_ptrs(self, exports: InstanceExports, *strings: str) -> Tuple[int]:
        """Generate a pointer to a string"""
        ptr_list = []
        for string in strings:
            string = bytes(string, "utf-8")
            string_len = len(string) + 1
            string_pointer = exports.get("allocate")(self.store, string_len)
            exports["memory"].write(self.store, string, string_pointer)
            ptr_list.append((string_pointer, string_len))
        try:
            yield tuple([ptr_info[0] for ptr_info in ptr_list])
        finally:
            for string_pointer, string_len in ptr_list:
                exports.get("deallocate")(self.store, string_pointer, string_len)

    def _get_str_from_ptr(self, exports: InstanceExports, ptr: int) -> str:
        byte_list = []
        start = ptr

        while True:
            code = exports["memory"].data_ptr(self.store)[start]
            if code == 0:
                break
            byte_list.append(code)
            start += 1

        exports.get("deallocate")(self.store, ptr, len(byte_list))

        return bytes(byte_list).decode()

    def get_sql_from_payload(self, table_name: str, payload: Dict[str, Any]) -> str:
        """Get SQL from payload on wasm"""
        instance = self.linker.instantiate(self.store, self.module)
        exports = instance.exports(self.store)

        with self._gen_str_ptrs(exports, table_name, json.dumps(payload)) as (table_name_ptr, payload_ptr):
            result_ptr = exports.get("parser_dsl_with_table")(
                self.store,
                table_name_ptr,
                payload_ptr,
            )
            return self._get_str_from_ptr(exports, result_ptr)


dsl_to_wasm = DslToSqlWasm()


def get_sql_from_payload(table_name: str, payload: Dict[str, Any]) -> str:
    """Get SQL from payload"""
    return dsl_to_wasm.get_sql_from_payload(table_name, payload)
