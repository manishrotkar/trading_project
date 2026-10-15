from agent import get_user_request

print("INPUT TEST")
print("Enter = submit")
print("Shift+Enter = new line")
print("Ctrl+C = cancel")

try:
    result = get_user_request()
    print("\nRESULT:")
    print(repr(result))
except EOFError:
    print("\nEXIT")
