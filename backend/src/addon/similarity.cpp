#include <napi.h>
#include <vector>
#include <cmath>

Napi::Value CalculateCosineSimilarity(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();

    if (info.Length() < 2) {
        Napi::TypeError::New(env, "Wrong number of arguments").ThrowAsJavaScriptException();
        return env.Null();
    }

    if (!info[0].IsArray() || !info[1].IsArray()) {
        Napi::TypeError::New(env, "Arguments must be arrays").ThrowAsJavaScriptException();
        return env.Null();
    }

    Napi::Array arrA = info[0].As<Napi::Array>();
    Napi::Array arrB = info[1].As<Napi::Array>();

    uint32_t lenA = arrA.Length();
    uint32_t lenB = arrB.Length();

    if (lenA != lenB || lenA == 0) {
        return Napi::Number::New(env, 0.0);
    }

    double dot = 0.0;
    double magA = 0.0;
    double magB = 0.0;

    for (uint32_t i = 0; i < lenA; i++) {
        Napi::Value valA = arrA[i];
        Napi::Value valB = arrB[i];

        if (!valA.IsNumber() || !valB.IsNumber()) {
            Napi::TypeError::New(env, "Array elements must be numbers").ThrowAsJavaScriptException();
            return env.Null();
        }

        double a = valA.As<Napi::Number>().DoubleValue();
        double b = valB.As<Napi::Number>().DoubleValue();

        dot += a * b;
        magA += a * a;
        magB += b * b;
    }

    if (magA == 0.0 || magB == 0.0) {
        return Napi::Number::New(env, 0.0);
    }

    double similarity = dot / (std::sqrt(magA) * std::sqrt(magB));
    return Napi::Number::New(env, similarity);
}

Napi::Object Init(Napi::Env env, Napi::Object exports) {
    exports.Set(Napi::String::New(env, "calculateCosineSimilarity"),
                Napi::Function::New(env, CalculateCosineSimilarity));
    return exports;
}

NODE_API_MODULE(similarity, Init)
