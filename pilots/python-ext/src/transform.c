/* 试点工程 3（Python C 扩展 / setuptools build_ext / P2）。
 *
 * 双模式（同 integrations/python/example 模式）：
 *   - 定义 ANTI_REA_EXT -> 构建为 Python C 扩展（setuptools 传宏）；
 *   - 未定义           -> 构建为独立程序（集成驱动保护并做差分验证）。
 * 受保护函数 secret_key_schedule 命中 secret 规则；仅演示用途。 */
#include <stdint.h>
#include <stdio.h>

int secret_key_schedule(int seed)
{
    int k0 = 0x37, k1 = 0x11, k2 = 0x6d, k3 = 0x5b;
    int y = seed ^ k0;
    y = (y * 0x1d) + k1;
    y = y ^ k2;
    y = (y << 2) ^ k3;
    return y;
}

#ifdef ANTI_REA_EXT

#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *py_transform(PyObject *self, PyObject *args)
{
    long v;
    (void)self;
    if (!PyArg_ParseTuple(args, "l", &v)) {
        return NULL;
    }
    return PyLong_FromLong(secret_key_schedule((int)v));
}

static PyMethodDef Methods[] = {
    {"transform", py_transform, METH_VARARGS, "apply secret transform"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "pilotext", NULL, -1, Methods
};

PyMODINIT_FUNC PyInit_pilotext(void)
{
    return PyModule_Create(&moduledef);
}

#else

int main(void)
{
    printf("%d\n", secret_key_schedule(7));
    return 0;
}

#endif
