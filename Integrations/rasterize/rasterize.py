import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import sys
import base64

PROXY = demisto.getParam('proxy')

if PROXY:
    HTTP_PROXY = os.environ.get('http_proxy')
    HTTPS_PROXY = os.environ.get('https_proxy')

WITH_ERRORS = demisto.params().get('with_error', True)
DEFAULT_STDOUT = sys.stdout

URL_ERROR_MSG = "Can't access the URL. It might be malicious, or unreachable for one of several reasons. " \
                "You can choose to receive this message as error/warning in the instance settings"


def init_driver():
    demisto.debug('Creating chrome driver')
    try:
        with open('log.txt', 'w') as log:
            sys.stdout = log
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--hide-scrollbars')
            chrome_options.add_argument('--disable_infobars')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--start-fullscreen')
            chrome_options.add_argument('--ignore-certificate-errors')

            driver = webdriver.Chrome(options=chrome_options)
    except Exception as ex:
        return_error(str(ex))
    finally:
        sys.stdout = DEFAULT_STDOUT

    demisto.debug('Creating chrome driver - COMPLETED')
    return driver


def rasterize(path: str, width: int, height: int, r_type='png'):
    driver = init_driver()

    try:
        demisto.debug('Navigating to url')

        driver.get(path)
        driver.implicitly_wait(5)

        demisto.debug('Navigating to url - COMPLETED')

        if r_type.lower() == 'pdf':
            output = get_pdf(driver, width, height)
        else:
            output = get_image(driver, width, height)

        return output

    except NoSuchElementException as ex:
        if 'invalid argument' in str(ex):
            return_error(URL_ERROR_MSG) if WITH_ERRORS else return_warning(URL_ERROR_MSG)

        return_error(str(ex)) if WITH_ERRORS else return_warning(str(ex))


def get_image(driver, width: int, height: int):
    demisto.debug('Capturing screenshot')

    # Set windows size
    driver.set_window_size(width, height)

    image = driver.get_screenshot_as_png()
    driver.quit()

    demisto.debug('Capturing screenshot - COMPLETED')

    return image


def get_pdf(driver, width: int, height: int):
    demisto.debug('Generating PDF')

    driver.set_window_size(width, height)
    resource = f'{driver.command_executor._url}/session/{driver.session_id}/chromium/send_command_and_get_result'
    body = json.dumps({'cmd': 'Page.printToPDF', 'params': {'landscape': False}})
    response = driver.command_executor._request('POST', resource, body)

    if response.get('status'):
        demisto.results(response.get('status'))
        return_error(response.get('value'))

    data = base64.b64decode(response.get('value').get('data'))
    demisto.debug('Generating PDF - COMPLETED')

    return data


def rasterize_command():
    url = demisto.getArg('url')
    w = demisto.args().get('width', 600)
    h = demisto.args().get('height', 800)
    r_type = demisto.args().get('type', 'png')

    if not (url.startswith('http')):
        url = f'http://{url}'
    filename = f'url.{"pdf" if r_type == "pdf" else "png"}'  # type: ignore
    proxy_flag = ""
    if PROXY:
        proxy_flag = f"--proxy={HTTPS_PROXY if url.startswith('https') else HTTP_PROXY}"  # type: ignore
    demisto.debug('rasterize proxy settings: ' + proxy_flag)

    output = rasterize(path=url, r_type=r_type, width=w, height=h)
    file = fileResult(filename=filename, data=output)

    demisto.results(file)


def rasterize_image_command():
    entry_id = demisto.args().get('EntryID')
    w = demisto.args().get('width', 600)
    h = demisto.args().get('height', 800)

    file_path = demisto.getFilePath(entry_id).get('path')
    filename = 'image.png'  # type: ignore

    with open(file_path, 'rb') as f, open('output_image', 'w') as image:
        data = base64.b64encode(f.read()).decode('utf-8')
        image.write(data)
        output = rasterize(path=f'file://{os.path.realpath(f.name)}', width=w, height=h)
        file = fileResult(filename=filename, data=output)

        demisto.results(file)


def rasterize_email_command():
    html_body = demisto.args().get('htmlBody')
    w = demisto.args().get('width', 600)
    h = demisto.args().get('height', 800)
    r_type = demisto.args().get('type', 'png')

    filename = f'email.{"pdf" if r_type.lower() == "pdf" else "png"}'  # type: ignore
    with open('htmlBody.html', 'w') as f:
        f.write(f'<html style="background:white";>{html_body}</html>')
    path = f'file://{os.path.realpath(f.name)}'

    output = rasterize(path=path, r_type=r_type, width=w, height=h)
    file = fileResult(filename=filename, data=output)

    demisto.results(file)


def test():
    # setting up a mock email file
    with open('htmlBodyTest.html', 'w') as test_file:
        test_file.write('<html><head><meta http-equiv=\"Content-Type\" content=\"text/html;charset=utf-8\">'
                        '</head><body><br>---------- TEST FILE ----------<br></body></html>')
        file_path = f'file://{os.path.realpath(test_file.name)}'

    # rasterizing the file
    driver = init_driver()
    driver.get(file_path)
    driver.implicitly_wait(5)
    driver.set_window_size(250, 250)
    driver.get_screenshot_as_png()
    driver.quit()

    demisto.results('ok')


def main():
    try:
        if demisto.command() == 'test-module':
            test()

        elif demisto.command() == 'rasterize-image':
            rasterize_image_command()

        elif demisto.command() == 'rasterize-email':
            rasterize_email_command()

        elif demisto.command() == 'rasterize':
            rasterize_command()

        else:
            return_error('Unrecognized command')

    except Exception as ex:
        return_error(str(ex))

    finally:  # just to be extra safe
        sys.stdout = DEFAULT_STDOUT


if __name__ in ["__builtin__", "builtins"]:
    main()
