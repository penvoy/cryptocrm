import base64
import hmac
import json
import time
import datetime
import random
from django.shortcuts import render
import requests
import jwt
import hashlib

from pybit.unified_trading import HTTP

from django.contrib.auth.decorators import login_required

from .models import Balance


def get_сurrency_rate(token, host, currency):
    params={"limit":"500"}
    response = requests.get('https://' + host + '/api/v2/trades/my',
                            headers = {'Authorization': 'Bearer ' + token}, json=params, timeout=5)
    
    if response.status_code == 200:
        response_data = response.json()
        market = (item for item in response_data if item.get("currency") == currency)
        first_item = next(market, None)
        if first_item:
            return first_item.get("price")


def get_token(uid, key, host=None):
    key = base64.b64decode(key)
    iat = int(time.mktime(datetime.datetime.now().timetuple()))

    claims = {
        "exp": iat + 5*60*60, # JWT Request TTL in seconds since epoch
        "jti": hex(random.getrandbits(12)).upper()
    }

    jwt_token = jwt.encode(claims, key, algorithm="RS256")
    
    if host:
        response = requests.post('https://dauth.' + host + '/api/v1/sessions/generate_jwt',
                         json={'kid': uid, 'jwt_token': jwt_token}, timeout=5)
    else:
        headers = {
    "accept": "application/json",
    "content-type": "application/json"
    }
        
        response = requests.post("https://api.rapira.net/open/generate_jwt", headers=headers, json={'kid': uid, 'jwt_token': jwt_token})


    token = response.json().get('token')

    return token


def get_balance_garantex(uid, private_key):
    host = 'garantex.org' 

    token = get_token(uid, private_key, host)

    response = requests.get('https://' + host + '/api/v2/accounts',
                    headers = {'Authorization': 'Bearer ' + token}, timeout=5)
    result = 0
    locked = 0
    usdt_balance = 0
    for coin in response.json():
        if float(coin.get("balance")) > 0:
            print(coin)
            if coin.get("currency") == 'usdt':
                # вывести наверх, когда будет ясность с курсом
                result += float(coin.get("balance"))
                locked += float(coin.get("locked"))
                usdt_balance = float(coin.get("balance"))
            else:
                price = get_сurrency_rate(token, host, coin.get("currency"))
                if price:
                    price = float(price)
                    if coin.get("currency").startswith("usd"):
                        print("got usd")
                        result += float(coin.get("balance"))
                        locked += float(coin.get("locked"))
                    elif coin.get("currency") == "rub":
                        result += (float(coin.get("balance")) // price)
                        locked += (float(coin.get("locked")) // price)
                    else:
                        result += (float(coin.get("balance")) * price)
                        locked += (float(coin.get("locked")) * price)

    return ({
        "result": result,
        "locked": locked,
        "usdt_balance": usdt_balance
        })

def get_rates_rapira(currency):
    url = "https://api.rapira.net/open/market/rates" 
    response = requests.get(url=url, headers={"accept": "application/json"}, timeout=5)

    if response.status_code == 200:
        response_data = response.json()
        market_data = response_data.get("data", [])
        
        for item in market_data:
            if item.get("quoteCurrency") == currency and item.get("baseCurrency") == 'USDT':
                rate = item.get("close")
                return rate




def get_balance_rapira(uid, secret):
    token = get_token(uid, secret)
    url = "https://api.rapira.net/open/wallet/balance"

    headers = {"accept": "application/json", 'Authorization': 'Bearer ' + token}

    response = requests.get(url, headers=headers, timeout=5)

    result = 0
    locked = 0
    usdt_balance = 0


    for coin in response.json():
        if float(coin.get("balance")) > 0:
            if coin.get("unit") == 'USDT':
                result += float(coin.get("balance"))
                locked += float(coin.get("frozenBalance"))
                usdt_balance = float(coin.get("balance"))

            else:
                rate = get_rates_rapira(coin.get("unit"))
                if rate:
                    rate = float(rate)
                    available_in_usdt = float(coin.get("balance")) * rate
                    freeze_in_usdt = float(coin.get("frozenBalance")) * rate
                    
                    result += available_in_usdt
                    locked += freeze_in_usdt

    return ({
        "result": result,
        "locked": locked,
        "usdt_balance": usdt_balance
        })



def get_balance_bb(api_key, api_secret, accountType):
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
        max_retries=5,
        retry_delay=5,
        )
    try:
        response = session.get_wallet_balance(
            accountType=accountType)
    except Exception as e:
        raise e
    else:
        result = response.get("result")
        if result:
            if result.get("list"):
                result = result["list"][0]
                total = float(result.get("totalWalletBalance", 0))
                coins = result.get("coin", [])
                total_usdt = 0
                for coin in coins:
                    if coin.get("coin") == "USDT":
                        total_usdt = float(coin.get("walletBalance"))
                return (
                    {
                        "result":total,
                        "locked": 0,
                        "usdt_balance": total_usdt
                    }
                )


def get_balance_cryptomus(merchant_id, api_key):
    params = ""
    encoded_data = (base64.b64encode(params.encode("utf-8")).decode("utf-8") + f"{api_key}").encode("utf-8")


    sign = hashlib.md5(encoded_data).hexdigest()

    headers = {"merchant": merchant_id, 'sign': sign, "Content-Type": "application/json"}

    url = 'https://api.cryptomus.com/v1/balance'

    response = requests.post(url=url, headers=headers)
    if response.status_code == 200:
        response_data = response.json().get("result")[0]
        balance = response_data.get("balance")
        result = 0
        locked = 0
        usdt_balance = 0
        full_list = balance.get("merchant") + balance.get("user")
        for coin in full_list:
            if float(coin.get("balance")) > 0:
                result += float(coin.get("balance_usd"))
                if coin.get("currency_code") == 'USDT':
                    usdt_balance = float(coin.get("balance"))
        return ({
            "result": result,
            "locked": locked,
            "usdt_balance": usdt_balance
            })
    

def get_available_markets_whitebit(url):

    url = url + '/api/v4/public/ticker'

    response = requests.get(url, timeout=5)

    if response.status_code == 200:

        response_data = json.dumps(response.json(), sort_keys=True, indent=4)

        return response_data

def get_balance_whitebit(secret_key, api_key):
    # request = '/api/v4/trade-account/balance'  # put here request path. For obtaining trading balance use: /api/v4/trade-account/balance
    request = '/api/v4/main-account/balance'
    baseUrl = 'https://whitebit.com'  # domain without last slash. Do not use https://whitebit.com/
    # If the nonce is similar to or lower than the previous request number, you will receive the 'too many requests' error message
    nonce = time.time_ns() // 1_000_000  # nonce is a number (preferrably epoch time in milliseconds) that is always higher than the previous request number

    data = {
        'request': request,
        'nonce': nonce,
        'nonceWindow': True  # the api will validate that your nonce enter the range of current time +/- 5 seconds
    }

    # preparing request URL
    completeUrl = baseUrl + request

    data_json = json.dumps(data, separators=(',', ':'))  # use separators param for deleting spaces
    payload = base64.b64encode(data_json.encode('ascii'))
    signature = hmac.new(secret_key.encode('ascii'), payload, hashlib.sha512).hexdigest()

    # preparing headers
    headers = {
        'Content-type': 'application/json',
        'X-TXC-APIKEY': api_key,
        'X-TXC-PAYLOAD': payload,
        'X-TXC-SIGNATURE': signature,
    }

    # sending request
    response = requests.post(completeUrl, headers=headers, data=data_json, timeout=5)

    if response.status_code == 200:
        
        markets = get_available_markets_whitebit(baseUrl)
        if markets:
            markets = json.loads(markets)
            result = 0
            locked = 0
            usdt_balance = 0
            for key, value in response.json().items():
                if value.get("main_balance") > "0":
                    if key == 'USDT':
                        result += float(value.get("main_balance"))
                        usdt_balance = float(value.get("main_balance"))
                    else:
                        for market, price in markets.items():
                            if market.startswith(key) and market.endswith("USDT"):
                                course = price.get("last_price")
                                if course:
                                    course = float(course)
                                    available_in_usdt = float(value.get("main_balance")) * course

                                    result += available_in_usdt

                            
                    
            return ({
                    "result": result,
                    "locked": locked,
                    "usdt_balance": usdt_balance
                    })

# TO DO// сделать получение с байбита 
# написать шаблоны (вход, баланс, настройки(добавление юзеров, добавление бирж))

@login_required
def get_balance(request):
    if request.method == "POST":
        accounts_data = [
        {
            "name":"garantex",
            "uid":"64072430-c44b-48e2-a852-596529904858",
            "key":"LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcFFJQkFBS0NBUUVBOFBZSGREblVZMzBieHVhTzBWVTFoeG42TjRkeHpmN1dvVFlHb3ZWeWp2ZC9XUGFRCm9mKzVDRDdXU21YLzBSR0xQVEdlVStQdldKOXZGVjJwb0N6a0VxcWY2bEE1cWVOSk1hL0xQdnhqd1dWaXB6cEMKYUh1b0wrTUlyNHRMeGRENXpjZDV2T0RIZU1KbzJuNWlxUWRmNS9YZFVvaTdxdGVIWW1xQkYxeTZ2ajdpOHJERQp4b3NxMTRCcThGcmdRcld4OVZtcXd0VGhuenZIU3UremkxYS84cFNTbEdtRmg3RDIzWldiRmVWeEVqSGZlbFBmCmpkR2FDdDEzY3B5SWdtcVluMGFsN3g2aVozaHVQeGZVZUdhVGV0eWhpSXF5U0hka2pkMHVGQzJZSTJ6WU1sdFMKN2hLSlNxazNKaVZhYW9mclNOMmorN3d6Vkh4c2dwakdoOW1GcHdJREFRQUJBb0lCQUFuQ3h4RDUvaTd1Rkp0NAo1WTBuQUNwU0FFeE11MVZta0VmVHlLanlucXFDN2RDOGhnTGszQ1BxcjFwZS9nVFZlVlBJSVAvT3NENCtrTysxCjIvL0k2bmh0MVJNb2syNGlrYU95Tm5XZ2ZXN25XYzAwSEMrT1V5ZnlLdkZRWlNzb0FBTGhkaUY4RXN0bUFXVncKRUpHRVl0S3VFRGFZZElsVWlkYlZ6UC9tOUFvb0ljVFRueUZ4QUJOMzZRTzlJY3I2ZVFvZllQL1RoOCt5YVZxUwoxdnpoM2wzK0hkTjR1amRVbkJlbE80ZWpySVNZaCtBUStXTzB2VXNrSFdYWXczL2RIWk82bytFWmpFa1I3R1ZyCjhlYXRDcjVLN2g4OG9uVUY1S1l1REhvd1R3S1cwT1ZlYXBNZHhpcnBOU2s3cXZwajVPTHVJdStEdWtWUUUrZEgKWmdHMjBUa0NnWUVBLzBwWEFXZk5iSjRPdWt3SUZJQWpLd0tTNFM1WnBCTUhLdDY2Nk83SncyNnpIMWRTcjVKQQphKzVzUlhmVnpMNlcwaTVEeUV0aUwrSVRqUXJNaDBGWW82eDBzNml6Q1VoWnNmWGpTdkt2TTFYalNaa3M0cU5BClRFQ3UxUHVjcjZ1UVhTSVpha2paT0xwenh0OHJURk4zbEd4b2Y4MlpDQVpVTHVZRmNuZ0NLZDhDZ1lFQThhRisKSkxKeGFyMm83SmJxRFdEOFhLRFUraWsyaytNK0xMU1pDSXZrRkFKZlNwZjNERi96UjFmQnZRdnpLWTNIYlB4aAozUXZzR0M3d08rMS9UYWlLck8wRGF2Qkh1VnQzRlBXbzA3c3QzR0pldmx1K0JuZmRHYXUzVDlRMFlKdXBrQXVuCjJwN1ZxcEFldFk0S1U3VC9leThkRG4ybFVvRXU3ak85Y2ZZK0xUa0NnWUVBak80cUY5R0krdVJLZHhmUUFoazIKME9DTDJ4bXVUTUJnWFk4MW1hOXczSjE0N3QxUy9TOTh0dGlaRnNSdjE2YUROaVpxTHVGR28rNW5JcDZLaUVSUAp2Wk5QblhxTTA1d0lRQkRnMkJnZkZmVGRFMTBuQlRwZ0hYZzd5OEhYSHJkVWE4V09TRGxOQ1Y4TTJRV01Mb2VKClpQdHZ1TlgwSEJUNlZpV1Bia0RIMlBzQ2dZRUEzYUVTNHZZSnNhNWsweDFaY1F3VWJhSFh0OTAxZ2xCZEp3US8KbWVjMlBHUXdvMnJmM3luakt2MERaek1leG02VkRSSXhjVjhPSHVCdTJZanR5MzFjTldEd1VaWXpNNEVCcU9mcgpBc29kTnBmRDd6YVhCYmZMeFZBTHc5MFFiY3hacXhZRjBERUFLb0ltcU1Dd0dEZGNYdERJQmhLWklTUDh0K0FkClUvcFk3WUVDZ1lFQTVUYTcrRTAvODFmeW9Wbm1EeU5MVTBlT0JCSENjWmJDOEgzVSswTm5BYWhVOVVXbnFqRmMKOEhDNHNSZ2pmUGh5dk1EVXcrbkZqM05mbFlGeGpZVXBGSzFOMldrY0xrZVJQYzlVanExcmhac0Q4M2JZWEJmdgp2T1dWT2lnaDhOVjVUdnRoMXA3Ri9kcXZGT29weDVucDFzQ3MvSVg2a0thS21xWE9RRDRyYndBPQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo="
        },
        {
            "name":"rapira",
            "uid":"7919eb47-6b25-440c-88c2-2ae8037c9c5b",
            "key":"LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFdlFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLY3dnZ1NqQWdFQUFvSUJBUUNSTmhaSU9JVTFiQ01MNjdJWlRxZTlPTURwTU5ZejhXYW1DbFJlaVFZSlVJWXJaZTZDbVQ0ZWxOMDkvb0RnMU9BSFRYWEJkZ2xCM2puSlpNRTh6bHA2OWd4aWVGYm13RUczRjMzZk03MEdjZzErYUM4YTk5cWNaQVdPL0hLc2IwQnNpK202SVowV2tnUWlhWnlCNEJ0MWtldmJGazl5Wmp5eDZ2YVZ3OFM3azByM3hNc1V5VnRaSEpibDlmdXVuWk9hTmZVMVZnSlZHVGRhdGIvZlo2N21jZ0IvVW04ME1HZjlTcGw0ZTR1U3U2UitpMkpLeUJrdlZxZ2xweWU0bnVyOXFyWk9nQXl1MEhTdGtobTcySEpSQ254dkhDMGlCWEpxL21lNWthVFR4WGdra3o0ZGlrRHlXQk40MzVkdzc3L0czSExqc1VXTUNIRjhpTUR1VTAvMUFnTUJBQUVDZ2dFQUNZQW9RV01QOVczL29GZUprd0NqbG95VjNvdnNtb0JvVHJrWDlRbHlXaWlwRVVJb01wRHBKZ3k4L3V5SVY4TEZ3am5qV0ViVjZ6ZlVGYnBMQkU5SFR6VTFtK1JlRElIaFZYa3ExSnJUZXJqNmxnaDdVSUNOT1RTTmJUZFV5Z3NMV1lRUlJPQWtkdEM5M0N5SEZMT1V5RmZ3UGxOOWhqRnNpNExMemF6OTBhY3VWTGppazlJL2RRdytkM1U0Z3J1eDZZcDc5RldqV0cxNmUySVI1aXlxdE02STIwN3Zrem8ySjdZY2NGYXlITXFFTjRsUWFKa3lSMmU3RGFqZEVoWGhDRkRwYXp3UDdwVDd6dUNmbTN3Q3dPWXBpRjJVbzRMdDQ0MDdsNzBUU1JlTTRSaXNRWHZOSm03eUFZTGdzRVZuczM1Ylg2bjlwdURlS2dwVWNvbE4zd0tCZ1FDNjJSUEJSQVFTSmgxblVBN0tnMkYySGNNbHZiMmNIQmdZbWR1WFRGZk9KTVJoV2RHb29Qc01sUFREQTR1dWtsTWhmVGU1MVZJWFBGNWJYbE9GaHVMOXppR2hVdTJ1dlVDSnpNU3FCVWVva2FScms5aW5GcExhRzFsTDNST2ZTK0IzTG1TTWZhUUpQMVZab1pXVHFKdUtOSXJRWTF5MEkxb2c2Rkc0ckpWeUl3S0JnUURHOUNQQzRBUDMzL29DdkdhZkxRaVhrUHVhSWZSaDF5a01KMlo4UTczWGt0MnhnVDJKUjRHOE5rSDh1RkNMN0xMRFRaT2Z2MDd0eUhYUjJGWllwdlNnell1QmZ0OGJOTDUwQnEyK21HaDVTczFiaGorc0puQ05FL2EzSDI0YjdmOTBTbXZlaGNGc0RqRk1iU2NUZkZjZDAxQWV5Skh4enZ0ekZWTW5TbmFiQndLQmdHQklPaGpPSHJibmN5Rm9yS2FJZXZGdHRzQzgvSGIwTnlwK0poeloxeWsvNHY0elZZbHFvdE5COHJxSEdqUno3R2lHYU8vV3ovMXZPMFFqNERBZmFOclduSmZQN3ZDclR4VnpNaWhXbmkxc0YyamovN0ZpUFh3c3VhQVJKT3BpSkNIbUF5UXVIaGd4elo1cFdIV0ZYZGtpNkNFb0FuNUU5VTJkeVhhN1lDczNBb0dCQUpyUkpIcml3M1BCOE5Uc01wY3UvZjZqcllZMVlldzQrQklqSHRjWUI4U1czcmpnTHppQ1VteFpkR1BxTVpPUTcxS1hMWWNqNFpHYmFrT1BLekgxU1d0UVIzelBjMkhDVzJvQ1FIV09OODRhN1U2SlcwYms2clI5a29EUmptZGhmbVhKKzhLL0p0S2xBS3ZPVEpnWEs5dGpzbmNoOEovUVIwODRpdXFLUVYxRkFvR0FMTUUrVmhDT0d4N084MXhaVUFWY0xDUjVxWGVKN0g4M3haM3NCTmkzVTRBUFFRTWFNWC8yNG43RHdBOXBWekxjT3RNcm9QTEZjZFBQejc3ZUUxV2dXei9FQi9aN3ZzS1pHbU9GOU9ybVBXNzVVWmVTOW9saTk5N1V3YTNzQW14UlV1MjRyekRDOW4vcndRVEtjeS9ka1o4UCtKRG43TmF1Tm9mWXFHZnlXcU09Ci0tLS0tRU5EIFJTQSBQUklWQVRFIEtFWS0tLS0tCg=="
        },
        {
            "name":"cryptomus",
            "uid":"b96f61cf-8ea9-4a50-b471-62a0f057bf03",
            "key":"n6C9BRrOs10B91ZdXwDv9XFEsZfrDLtB8x1WtpWs2gH4TR5h8nlU4c938Erml9QQpQurPkrOXuLQGFG3mTXGHcCQJb01dm5ZQnUommr7zzBUCZ5R5Xn7IMLCmJE5l3jm"
        },
        {
            "name":"whitebit",
            "uid":'227a51142975cdf9d04dbffa752145b0', # secret
            "key":'c09ae7e86682446722772d7dad2a043b' # api key 
        },
        {
            "name":"bybit",
            "uid":'UzbeUaa73FlFI5w2nemfYF1Eg40ntZPs0Dih', # secret
            "key":'LBiJMb8yAtNsZzwa7q',# api key
            "account" : "ББ Эмиль" 
        },
        {
            "name":"bybit",
            "uid":'SSMatCmRGozi5ybHz3tZvdY05nuP8ELAnw88', # secret
            "key":'eCGzXUFHYUEvf7QxKb',# api key
            "account": "ББ Илья" 
        },
        {
            "name":"bybit",
            "uid":'M7yqxz4O70G3k4t1lOXs0iuhzIuZ09Ckx6PD', # secret
            "key":'dsAsiOmKSBcAQmfe2a',# api key
            "account": "ББ Адель" 
        },
        {
            "name":"bybit",
            "uid":'pyOZGrgLnu2Ku0mdNia7Poty7VlDRDV6udxP', # secret
            "key":'aBQj2ZqqToqCLH2RKa',# api key
            "account": "ББ К" 
        },
        {
            "name":"bybit",
            "uid":'UzbeUaa73FlFI5w2nemfYF1Eg40ntZPs0Dih', # secret
            "key":'LBiJMb8yAtNsZzwa7q',# api key
            "account": "ББ Даши" 
        },
        {
            "name":"bybit",
            "uid":'E7nmFrSQyyNKys5YiApUrUnG2lC9biyLKGHp', # secret
            "key":'I8PFTbMg4vrLjYUIlB',# api key
            "account": "ББ Марат" ,
            "accountType" : "UNIFIED"
        }]

        result = 0
        locked = 0 
        response = {}
        try:
            for target in accounts_data:
                print(target.get("name"))
                uid = target.get("uid")
                key = target.get("key")
                if target.get("name") == 'garantex':
                    response_data = get_balance_garantex(uid, key)
                    response['garantex'] = response_data.get("usdt_balance", 0)

                if target.get("name") == 'cryptomus':
                    response_data = get_balance_cryptomus(uid, key)
                    response['cryptomus'] = response_data.get("usdt_balance", 0)

                if target.get("name") == 'whitebit':
                    response_data = get_balance_whitebit(uid, key)
                    response['whitebit'] = response_data.get("usdt_balance", 0)

                if target.get("name") == 'rapira':
                    response_data = get_balance_rapira(uid, key)
                    response['rapira'] = response_data.get("usdt_balance", 0)

                result += response_data.get("result")
                locked += response_data.get("locked")

                if target.get("name") == 'bybit':
                    accountType = target.get("accountType")
                    if accountType:
                        response_data = get_balance_bb(key, uid, accountType)

                        result += response_data.get("result")
                        locked += response_data.get("locked")
                        if response.get("bybit"):
                            response["bybit"] = response.get("bybit") + response_data.get("usdt_balance", 0)
                        else:
                            response['bybit'] = response_data.get("usdt_balance", 0)
                # result += response_data.get("result")
                # locked += response_data.get("locked")
        except Exception as e:
            print("ошибка")
            return render(request, 'errors/500.html', context={"error": str(e)})
        else:
            Balance.objects.create(data=response, result=result, locked=locked, date_created=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            return index(request)

@login_required
def index(request, page = 1, page_size = 12):

    # устанавливаем начальный индекс для среза
    start_index = (page - 1) * page_size

    # устанавливаем конечный индекс для среза
    end_index = page * page_size

    all_items = Balance.objects.all().order_by('-id')

    total = all_items.count()

    result = []
    for item in all_items[start_index:end_index]:
        result.append({
            "date_created": item.date_created, 
            "rapira": item.data.get("rapira", 0),
            "garantex":item.data.get("garantex", 0),
            "cryptomus": item.data.get("cryptomus", 0),
            "bybit": item.data.get("bybit", 0),
            "whitebit": item.data.get("whitebit", 0),
            "result":item.result,
            "locked": item.locked
                          })
        
    context = {"balances": result, "page": page, "total": total}
    return render(request, 'balance/index.html', context=context)
    


