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
            if coin.get("currency") == 'usdt':
                result += float(coin.get("balance"))
                locked += float(coin.get("locked"))
                usdt_balance += float(coin.get("balance"))
            else:
                price = get_сurrency_rate(token, host, coin.get("currency"))
                if price:
                    price = float(price)
                    if coin.get("currency").startswith("usd"):
                        result += float(coin.get("balance"))
                        locked += float(coin.get("locked"))
                    elif coin.get("currency") == "rub":
                        usdt_balance += (float(coin.get("balance")) // price)
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
            if currency == "RUB":
                if item.get("quoteCurrency") == 'USDT' and item.get("baseCurrency") == currency:
                    rate = item.get("close")
                    return rate
                
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
                usdt_balance += float(coin.get("balance"))

            else:
                rate = get_rates_rapira(coin.get("unit"))
                if rate:
                    rate = float(rate)
                    if coin.get("unit") == "RUB":
                        available_in_usdt = float(coin.get("balance")) // rate
                        freeze_in_usdt = float(coin.get("frozenBalance")) // rate
                        usdt_balance += available_in_usdt
                    else:
                        available_in_usdt = float(coin.get("balance")) * rate
                        freeze_in_usdt = float(coin.get("frozenBalance")) * rate
                    
                    result += available_in_usdt
                    locked += freeze_in_usdt

    return ({
        "result": result,
        "locked": locked,
        "usdt_balance": usdt_balance
        })



def get_rates_bb(session):
    try:
        response = session.get_tickers(
            category="spot"
        )
    except:
        return []
    else:
        result = response.get("result")
        if result:
            result_list = result.get("list", [])

            return result_list



# accountType = "UNIFIED"

# session = HTTP(
#         testnet=False,
#         api_key=api_key,
#         api_secret=api_secret,
#         max_retries=8,
#         retry_delay=5,
#         )

# print(session.get_spot_asset_info(
#     accountType="SPOT"))

def get_balance_bb(api_key, api_secret, accountType):
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
        max_retries=8,
        retry_delay=5,
        )
    try:
        response_coins = session.get_coins_balance(
                accountType="FUND")
        response_wallet = session.get_wallet_balance(
                accountType=accountType)
    except Exception as e:
        raise e
    else:
        result_coins = response_coins.get("result")
        result_wallet = response_wallet.get("result")

        if result_coins:
            result_coins = result_coins.get("balance")

        if result_wallet:
            if result_wallet.get("list"):
                result_wallet = result_wallet["list"][0]
                result_wallet = result_wallet.get("coin", [])

        result = result_wallet + result_coins

        total_usdt = 0
        total = 0

        rates = get_rates_bb(session)
        for coin in result:
            print(coin)
            if coin.get("coin") == "USDT":
                total += float(coin.get("walletBalance"))
                total_usdt += float(coin.get("walletBalance"))
            else:
                for rate in rates:
                    if (coin.get("coin") + "USDT") == rate.get("symbol"):
                        print(rate)
                        total += float(coin.get("walletBalance")) * float(rate.get("lastPrice"))

        return(
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
                    usdt_balance += float(coin.get("balance"))
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
    
def send_request(request, api_key, secret_key):
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

    return response


def get_balance_whitebit(secret_key, api_key):

    main_request = '/api/v4/main-account/balance'
    request_trading = '/api/v4/trade-account/balance'

    result = 0
    locked = 0
    usdt_balance = 0

    markets = get_available_markets_whitebit("https://whitebit.com")
    if markets:
        markets = json.loads(markets)
    trading_response = send_request(request_trading, api_key, secret_key)
    if trading_response.status_code == 200:
        for key, value in trading_response.json().items():
            if value.get("available") > '0':
                if key == 'USDT':
                    result += float(value.get("available"))
                    usdt_balance += float(value.get("available"))
                    locked += float(value.get("freeze"))
                else:
                    for market, price in markets.items():
                        if market.startswith(key) and market.endswith("USDT"):
                            course = price.get("last_price")
                            if course:
                                course = float(course)
                                available_in_usdt = float(value.get("available")) * course
                                freeze_in_usdt = float(value.get("freeze")) * course

                                result += available_in_usdt

        
    main_response = send_request(main_request, api_key, secret_key)
    if main_response.status_code == 200:  
        for key, value in main_response.json().items():
            if value.get("main_balance") > "0":
                if key == 'USDT':
                    result += float(value.get("main_balance"))
                    usdt_balance += float(value.get("main_balance"))
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


@login_required
def get_balance(request):
    if request.method == "POST":
        accounts_data = []

        result = 0
        locked = 0 
        total_bybit = 0
        response = {}
        try:
            for target in accounts_data:
                print(target.get("name"))
                uid = target.get("uid")
                key = target.get("key")
                if target.get("name") == 'garantex':
                    response_data = get_balance_garantex(uid, key)
                    response['garantex'] = response_data.get("result", 0)

                if target.get("name") == 'cryptomus':
                    response_data = get_balance_cryptomus(uid, key)
                    response['cryptomus'] = response_data.get("result", 0)

                if target.get("name") == 'whitebit':
                    response_data = get_balance_whitebit(uid, key)
                    response['whitebit'] = response_data.get("result", 0)

                if target.get("name") == 'rapira':
                    response_data = get_balance_rapira(uid, key)
                    response['rapira'] = response_data.get("result", 0)


                if target.get("name") == 'bybit':
                    accountType = target.get("accountType")
                    if accountType:
                        response_data = get_balance_bb(key, uid, accountType)
                        response_data['account'] = target.get("account")

                        if response.get("bybit"):
                            response["bybit"].append(response_data)
                        else:
                            response['bybit'] = [response_data]

                result += round(response_data.get("result"), 2)
                locked += round(response_data.get("locked"), 2)
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
    


