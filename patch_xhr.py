import re
with open(r'd:\CafeScraper\app\products\scraper\crawler.py', 'r', encoding='utf-8') as f:
    text = f.read()

xhr_code = '''
            // XHR Interceptor
            const XHR = XMLHttpRequest.prototype;
            const open = XHR.open;
            const send = XHR.send;
            XHR.open = function(method, url) {
                this._url = url;
                return open.apply(this, arguments);
            };
            XHR.send = function() {
                this.addEventListener('load', function() {
                    try {
                        window._api_responses.push({
                            url: this._url || "",
                            body: this.responseText || ""
                        });
                    } catch(e) {}
                });
                return send.apply(this, arguments);
            };
'''

text = text.replace('            return response;\n            };\n            \"\"\"', '            return response;\n            };\n' + xhr_code + '            \"\"\"')

with open(r'd:\CafeScraper\app\products\scraper\crawler.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Patched XHR interceptors')
