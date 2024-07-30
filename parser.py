import mechanicalsoup
import json

browser = mechanicalsoup.StatefulBrowser()
browser.open("https://storebucks.io/prmmxchngr")
browser.select_form('form[method="post"]')
browser["logmail"] = ""
browser["pass"] = ""
response = browser.submit_selected()
if response.text:
    encoded_data = json.loads((response.text))
    if encoded_data.get("status") == "success":
        admin_url = encoded_data.get("url", "")
        #print(browser.open(admin_url))
        if browser.open(admin_url).status_code == 200:
            result = {}
            browser.open("https://storebucks.io/wp-admin/admin.php?page=pn_bids&page_num=1")
            input_id = 99190
            full_id = "bidid_" + str(input_id)
            application = browser.page.find('div', class_="one_bids", id=full_id)



            




