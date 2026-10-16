/* Python 集成样例（FR-D5）
 *
 * 两种编译模式共用同一源文件：
 *   - 定义 ANTI_REA_EXT 时构建为 Python C 扩展（setuptools 传入宏）；
 *   - 未定义时构建为独立程序（REA-Shield 集成驱动保护并做差分验证）。
 */
#include <stdio.h>

long secret_mix(long x) {
    return (x * 7 + 3) ^ (x << 2);
}

#ifdef ANTI_REA_EXT

#include <Python.h>

static PyObject *py_secret_mix(PyObject *self, PyObject *args) {
    long x = 0;
    if (!PyArg_ParseTuple(args, "l", &x)) return NULL;
    return PyLong_FromLong(secret_mix(x));
}

static PyMethodDef Methods[] = {
    {"secret_mix", py_secret_mix, METH_VARARGS, "secret mix"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef Mod = {
    PyModuleDef_HEAD_INIT, "app", NULL, -1, Methods};

PyMODINIT_FUNC PyInit_app(void) { return PyModule_Create(&Mod); }

#else

int main(void) {
    printf("%ld\n", secret_mix(9));
    return 0;
}

#endif
