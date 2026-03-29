import sys
import qrcode

if len(sys.argv) < 2:
    print("Usage: python make_qr.py <url>")
    raise SystemExit(1)

url = sys.argv[1].strip()
img = qrcode.make(url)
img.save("project_test_qr.png")

print("Saved QR as project_test_qr.png")
print("URL:", url)