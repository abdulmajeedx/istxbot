package com.tiktokforbot.admin.data.api

/**
 * استثناء مخصص لأخطاء API.
 * يحمل رسالة عربية جاهزة للمستخدم النهائي.
 * toUserMessage() يتعرف عليه ولا يعيد تغليفه.
 */
class ApiException(
    message: String,
    val httpCode: Int = 0,
    val endpoint: String = ""
) : Exception(message)
