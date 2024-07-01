from django import template

register = template.Library() 

@register.simple_tag
def total_sum(values):
    total = 0
    
    for val in values:
        balance = val.get("usdt_balance", 0)
        total += balance

    return round(total, 2)