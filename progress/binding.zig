const std = @import("std");
const py = @cImport({
    @cDefine("PY_SSIZE_T_CLEAN", {});
    @cInclude("Python.h");
});

const ProgressObject = extern struct {
    ob_base: py.PyObject = .{},
    index: std.Progress.Node.OptionalIndex,
};

fn tp_init(op: *py.PyObject, args: [*c]py.PyObject, kwds: [*c]py.PyObject) callconv(.c) c_int {
    const keywords: [1][*c]u8 = .{null};
    if (py.PyArg_ParseTupleAndKeywords(args, kwds, ":__init__", @constCast(&keywords)) == 0)
        return -1;

    const self: *ProgressObject = @ptrCast(op);
    self.index = std.Progress.start(.{}).index;
    return 0;
}

fn start(op: [*c]py.PyObject, args: [*c]py.PyObject) callconv(.c) [*c]py.PyObject {
    var name: [*:0]u8 = undefined;
    var len: py.Py_ssize_t = undefined;
    var estimated_total_items: c_int = 0;

    if (py.PyArg_ParseTuple(args, "s#|i:start", &name, &len, &estimated_total_items) == 0)
        return null;

    const self: *ProgressObject = @ptrCast(op);
    const parent: std.Progress.Node = .{ .index = self.index };

    const node = parent.start(name[0..@abs(len)], @intCast(estimated_total_items));

    const result = py._PyObject_New(py.Py_TYPE(op)) orelse return null;
    const new: *ProgressObject = @ptrCast(result);
    new.index = node.index;
    return result;
}

fn end(op: [*c]py.PyObject, _: [*c]py.PyObject) callconv(.c) [*c]py.PyObject {
    const self: *ProgressObject = @ptrCast(op);
    const node: std.Progress.Node = .{ .index = self.index };
    node.end();
    return py.Py_None();
}

pub fn increase_estimate(op: [*c]py.PyObject, arg: [*c]py.PyObject) callconv(.c) [*c]py.PyObject {
    const count = py.PyLong_AsUnsignedLong(arg);
    if (count == std.math.maxInt(@TypeOf(count)) and py.PyErr_Occurred() != null)
        return null;
    const self: *ProgressObject = @ptrCast(op);
    const node: std.Progress.Node = .{ .index = self.index };
    node.increaseEstimatedTotalItems(count);
    return py.Py_None();
}

fn complete_one(op: [*c]py.PyObject, _: [*c]py.PyObject) callconv(.c) [*c]py.PyObject {
    const self: *ProgressObject = @ptrCast(op);
    const node: std.Progress.Node = .{ .index = self.index };
    node.completeOne();
    return py.Py_None();
}

const methods: [5]py.PyMethodDef = .{
    .{ .ml_name = "start", .ml_meth = &start, .ml_flags = py.METH_VARARGS },
    .{ .ml_name = "end", .ml_meth = &end, .ml_flags = py.METH_NOARGS },
    .{ .ml_name = "increase_estimate", .ml_meth = &increase_estimate, .ml_flags = py.METH_O },
    .{ .ml_name = "complete_one", .ml_meth = &complete_one, .ml_flags = py.METH_NOARGS },
    .{},
};

var slots: [3]py.PyType_Slot = .{
    .{ .slot = py.Py_tp_init, .pfunc = @constCast(&tp_init) },
    .{ .slot = py.Py_tp_methods, .pfunc = @constCast(&methods) },
    .{},
};

var Progress_TypeSpec: py.PyType_Spec = .{
    .name = "progress.Progress",
    .basicsize = @sizeOf(ProgressObject),
    .flags = py.Py_TPFLAGS_DEFAULT,
    .slots = &slots,
};

fn progress_modexec(m: [*c]py.PyObject) callconv(.c) c_int {
    const bases: ?*py.PyObject = null;
    const progress = py.PyType_FromModuleAndSpec(m, @ptrCast(&Progress_TypeSpec), bases) orelse return -1;
    const progress_type: [*c]py.PyTypeObject = @ptrCast(progress);
    if (py.PyModule_AddType(m, progress_type) < 0)
        return -1;
    py.Py_DECREF(progress);
    return 0;
}

var m_methods: [1]py.PyMethodDef = .{.{}};
var m_slots: [3]py.PyModuleDef_Slot = .{
    .{ .slot = py.Py_mod_exec, .value = @ptrCast(@constCast(&progress_modexec)) },
    .{ .slot = py.Py_mod_multiple_interpreters, .value = py.Py_MOD_PER_INTERPRETER_GIL_SUPPORTED },
    .{},
};

var progressmodule: py.PyModuleDef = .{
    .m_name = "progress",
    .m_methods = &m_methods,
    .m_slots = &m_slots,
};

pub export fn PyInit_progress() [*c]py.PyObject {
    return py.PyModuleDef_Init(&progressmodule);
}
