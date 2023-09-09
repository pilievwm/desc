from requests import get as original_get

global_counter = 0

def count_requests(func):
    def wrapper(*args, **kwargs):
        global global_counter  # make sure we are using the global counter
        global_counter += 1  # increment the counter
        print(f"Request #{global_counter} is made to: {args[0]}")
        return func(*args, **kwargs)  # execute the function
    
    return wrapper

# Wrap the original requests.get function
get = count_requests(original_get)