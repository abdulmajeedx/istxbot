<?php
namespace TikTokDL;

class ScraperValidator {

    public static function validate($url) {
        $result = ['success'=>false,'url'=>$url,'tested_at'=>current_time('mysql'),'steps'=>[],'video_url'=>null,'error'=>null,'duration_ms'=>0];
        $start = microtime(true);
        
        $s1 = self::check_url($url); $result['steps'][] = $s1;
        if (!$s1['passed']) { $result['error']=$s1['message']; $result['duration_ms']=round((microtime(true)-$start)*1000); return $result; }
        
        $s2 = self::fetch($url); $result['steps'][] = $s2;
        if (!$s2['passed']) { $result['error']=$s2['message']; $result['duration_ms']=round((microtime(true)-$start)*1000); return $result; }
        
        $html = $s2['data'];
        $found = false;
        
        $selectors = [
            'video_tag' => '/<video[^>]+src="([^"]+)"/i',
            'meta_og'   => '/<meta[^>]+property="og:video"[^>]+content="([^"]+)"/i',
            'json_ld'   => '/"contentUrl"\s*:\s*"([^"]+)"/',
            'regex'     => '/' . trim(Settings::get('selector_regex','/"playAddr[^"]*"([^"]+)"/'), '/') . '/i',
        ];
        
        foreach ($selectors as $name => $rx) {
            if (preg_match($rx, $html, $m)) {
                $vu = $m[1] ?? '';
                if (!empty($vu)) {
                    $result['steps'][] = ['name'=>$name,'type'=>'regex','passed'=>true,'message'=>"✅ Found via $name",'found'=>$vu];
                    $result['video_url'] = $vu; $found = true; break;
                }
            }
            $result['steps'][] = ['name'=>$name,'type'=>'regex','passed'=>false,'message'=>"❌ No match: $name"];
        }
        
        if (!$found) {
            $result['error'] = 'No video URL found. Update selectors.';
        } else {
            $s4 = self::verify_url($result['video_url']); $result['steps'][] = $s4;
            $result['success'] = $s4['passed'];
        }
        
        $result['duration_ms'] = round((microtime(true)-$start)*1000);
        return $result;
    }
    
    private static function check_url($url) {
        $ok = (bool)preg_match('/tiktok\.com|vm\.tiktok|douyin\.com/i', $url);
        return ['step'=>1,'name'=>'URL Check','passed'=>$ok,'message'=>$ok?'✅ Valid TikTok URL':'❌ Not a TikTok URL'];
    }
    
    private static function fetch($url) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_TIMEOUT=>20,
            CURLOPT_USERAGENT=>'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36']);
        $html = curl_exec($ch); $code = curl_getinfo($ch, CURLINFO_HTTP_CODE); $err = curl_error($ch); curl_close($ch);
        if ($code>=400||empty($html)) return ['step'=>2,'name'=>'Fetch Page','passed'=>false,'message'=>"❌ HTTP $code $err"];
        return ['step'=>2,'name'=>'Fetch Page','passed'=>true,'message'=>'✅ Page fetched ('.strlen($html).' bytes)','data'=>$html];
    }
    
    private static function verify_url($url) {
        if (empty($url)) return ['step'=>4,'name'=>'Verify Video','passed'=>false,'message'=>'❌ Empty URL'];
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_NOBODY=>true,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_TIMEOUT=>10,
            CURLOPT_USERAGENT=>'Mozilla/5.0 (Linux; Android 14)']);
        curl_exec($ch); $code = curl_getinfo($ch, CURLINFO_HTTP_CODE); $ct = curl_getinfo($ch, CURLINFO_CONTENT_TYPE); curl_close($ch);
        $ok = ($code>=200&&$code<400);
        return ['step'=>4,'name'=>'Verify Video','passed'=>$ok,'message'=>$ok?"✅ Valid (HTTP $code, $ct)":"❌ Invalid (HTTP $code)"];
    }
}
