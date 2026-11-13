"""Small source-only fixtures; no compiled programs are run by checks."""
JAVA = '''package demo;
import java.security.MessageDigest;
// Braces and fake code in comments: } void imaginary() { password = "fake";
public class Sample<T> {
    public Sample() {}
    public int run(int value) { return value; }
    public int run(String value) { return value.length(); }
    public void inspect(int a, int b, int c, int d, int e, int f) throws Exception {
        String password = "fixture-value";
        String explanation = "TODO: not a comment; void invented() {}";
        MessageDigest.getInstance("MD5");
        // TODO review this branch
        if (a > 0 && b > 0) { System.out.println(password); }
    }
    interface Reader { int read(); }
}
record Point(int x, int y) {}
'''
GO = '''package demo
import (
    "fmt"
    digest "crypto/md5"
)
type Worker[T any] struct { Value T }
type Reader interface { Read(p []byte) (int, error) }
func (w *Worker[T]) Run(a, b, c, d, e, f int) int {
    password := "fixture-value"
    fmt.Println(password)
    digest.Sum([]byte(password))
    // TODO simplify
    if a > 0 && b > 0 { return a }
    return b
}
func Identity[T any](value T) T { return value }
'''
CPP = '''#include <cstring>
#include <string>
namespace demo {
template<class T>
class Box {
public:
    Box() {}
    ~Box() {}
    T get() const { return T{}; }
    void later();
};
using Count = int;
int copy(char *target, const char *input, int a, int b, int c, int d) {
    const char *password = "fixture-value";
    const char *explanation = R"(TODO: } int invented() { strcpy(a,b);)";
    // TODO bound the operation
    strcpy(target, input);
    return a > b ? a : b;
}
}
'''
SOURCES = {'Sample.java': JAVA, 'worker.go': GO, 'sample.cpp': CPP,
           'sample.hpp': '#pragma once\nstruct Header { int field; };\nint declared(int value);\n'}
