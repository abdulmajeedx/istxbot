package com.tiktokforbot.admin.data.api

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.tiktokforbot.admin.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.JavaNetCookieJar
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.net.CookieManager
import java.net.CookiePolicy
import java.util.concurrent.TimeUnit

object RetrofitClient {

    // التوكن يُخزن هنا بعد تسجيل الدخول
    var adminToken: String = ""

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG)
            HttpLoggingInterceptor.Level.BODY
        else
            HttpLoggingInterceptor.Level.NONE
    }

    // مدير الكوكيز لدعم جلسات Flask (Session-based auth)
    private val cookieManager = CookieManager().apply {
        setCookiePolicy(CookiePolicy.ACCEPT_ALL)
    }

    private val okHttpClient = OkHttpClient.Builder()
        .cookieJar(JavaNetCookieJar(cookieManager))
        .addInterceptor { chain ->
            // إضافة Content-Type و Accept لكل الطلبات
            val original = chain.request()
            val request = original.newBuilder()
                .header("Accept", "application/json")
                .apply {
                    if (original.body != null && original.header("Content-Type") == null) {
                        header("Content-Type", "application/json")
                    }
                    // إضافة User-Agent لتجنب حظر بعض السيرفرات
                    if (original.header("User-Agent") == null) {
                        header("User-Agent", "TikTokForBot-Admin/1.0")
                    }
                    // إضافة توكن الأدمن للمصادقة
                    if (adminToken.isNotEmpty() && original.header("X-Admin-Token") == null) {
                        header("X-Admin-Token", adminToken)
                    }
                }
                .build()
            try {
                chain.proceed(request)
            } catch (e: java.net.UnknownHostException) {
                throw java.net.UnknownHostException("تعذر الوصول إلى السيرفر: تحقق من اتصال الإنترنت")
            } catch (e: javax.net.ssl.SSLHandshakeException) {
                throw javax.net.ssl.SSLHandshakeException("خطأ في شهادة SSL - قد يكون السيرفر يستخدم شهادة ذاتية")
            } catch (e: java.net.SocketTimeoutException) {
                throw java.net.SocketTimeoutException("انتهت مهلة الاتصال - السيرفر لا يستجيب")
            } catch (e: java.net.ConnectException) {
                throw java.net.ConnectException("فشل الاتصال بالسيرفر - تأكد من عنوان السيرفر")
            }
        }
        .addInterceptor { chain ->
            // كشف استجابات HTML من نوع المحتوى فقط (لا نستهلك الجسم!)
            val request = chain.request()
            val response = chain.proceed(request)
            val contentType = response.header("Content-Type") ?: ""

            // إذا كان المحتوى HTML، ارفض فوراً قبل أن يحاول Retrofit تحليله
            if (!response.isSuccessful && contentType.contains("text/html", ignoreCase = true)) {
                val code = response.code
                val path = request.url.encodedPath
                response.close() // نغلق الجسم لأننا لن نستخدمه
                val msg = when (code) {
                    404 -> "المسار غير موجود (404)\nالمسار: $path\nتأكد من أن السيرفر يعمل وعنوان API صحيح"
                    500 -> "خطأ داخلي في السيرفر (500)\nراجع سجلات السيرفر"
                    502 -> "بوابة غير صالحة (502)\nالسيرفر الخلفي معطل"
                    503 -> "الخدمة غير متاحة (503)\nالسيرفر قيد الصيانة"
                    else -> "السيرفر أرجع HTML (كود $code)\nالمسار: $path"
                }
                throw ApiException(msg, httpCode = code, endpoint = path)
            }
            response
        }
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .followRedirects(true)
        .followSslRedirects(true)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val apiService: BotApiService = retrofit.create(BotApiService::class.java)

    fun clearSession() {
        adminToken = ""
        cookieManager.cookieStore.removeAll()
    }
}
