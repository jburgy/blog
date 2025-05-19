---
marp: true
theme: uncover
_class: invert
---

![w:512](https://pydust.fulcrum.so/assets/ziggy-pydust.png)
### Moving past Zig 0.11

---
<style scoped>
section { columns: 2; display: block; }
h3 { break-before: column; margin-top: 0; }
</style>

### Context
- Python is _getting faster_
- Still write C extensions
- CPython makes it "easy"
- But Lots of boilerplate

### Official docs
```c
static PyMethodDef SpamMethods[] = {
    {"system", spam_system, METH_VARARGS,
     "Execute a shell command."},
    {NULL, NULL, 0, NULL} 
};

static struct PyModuleDef spammodule = {
    PyModuleDef_HEAD_INIT,
    "spam",
    spam_doc,
    -1,
    SpamMethods
};

PyMODINIT_FUNC
PyInit_spam(void)
{
    return PyModule_Create(&spammodule);
}
```

---
<style scoped>
section { columns: 2; display: block; }
h3 { break-before: column; margin-top: 0; }
</style>

### Zig is better C
- Comptime code gen
- Enter Ziggy Pydust
- Look ma, no boilerplate

### Mandatory Example
```c
const py = @import("pydust");

pub fn hello() !py.PyString {
    return try py.PyString.create("Hello!");
}

comptime {
    py.rootmodule(@This());
}
```

---

## Behind the scenes

```c
/// Register a Pydust module as a submodule to an existing module.
pub fn module(comptime definition: type) @TypeOf(definition) {
    State.register(definition, .module);  // ← global comptime mutable state!
    return definition;
}

// discovery.zig
pub const State = blk: {
    comptime var definitions: [1000]Definition = undefined;
    comptime var definitionsSize: usize = 0;

    break :blk struct {
        pub fn register(
            comptime definition: type,
            comptime deftype: DefinitionType,
        ) void {
            definitions[definitionsSize] = .{ .definition = definition, .type = deftype };
            definitionsSize += 1;
        }
        //...
    }
```
---
<style scoped>
section { columns: 2; display: block; }
h3 { break-before: column; margin-top: 0; }
</style>

### Stuck on Zig 0.12
- [Zig 0.12](https://github.com/ziglang/zig/pull/19414) bans
global comptime mutable state ⇒ different approach
- Replace global `State` by "viral" `type` parameter

### Timeline
* 2/24 Start [discussion](https://github.com/spiraldb/ziggy-pydust/discussions/428)
* 2/26 Raise [#429](https://github.com/spiraldb/ziggy-pydust/pull/429)
* 2/26 Builds (?!?)
* 3/30 Got something
* 4/02 All but 1 tests
* 4/29 All tests
* 4/29 Merged!
* 4/30 Python 3.13
* 5/10 Zig 0.14

---

<style scoped>
section { columns: 2; display: block; }
h3 { break-before: column; margin-top: 0; }
</style>

### Before
```c
const py = @import("pydust");

pub fn hello() !py.PyString {
    return try py.PyString.create("Hello!");
}

comptime {
    py.rootmodule(@This());
}
```

### After 
```c
const py = @import("pydust");
const root = @This();

pub fn hello() !py.PyString(root) {
    return try py.PyString(root).create("Hello!");
}

comptime {
    py.rootmodule(root);
}
```

---
## Longer version
![w:512](./pydust.png)
