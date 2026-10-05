"""Render the checked-in vector identity into the native multi-resolution icon."""
from pathlib import Path
import tempfile
import sys
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='edryvo-icon-') as directory:
        png = Path(directory) / 'icon.png'
        svg = (ROOT / 'web/assets/lumen.svg').read_text(encoding='utf-8')
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel='msedge' if sys.platform == 'win32' else None)
            page = browser.new_page(viewport={'width':256,'height':256}, device_scale_factor=1)
            page.set_content('<style>body{margin:0}svg{width:256px;height:256px;display:block}</style>' + svg)
            page.locator('svg').screenshot(path=str(png), omit_background=True)
            browser.close()
        with Image.open(png) as image:
            image.save(ROOT / 'web/assets/lumen.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print('Icono de Edryvo generado desde el SVG.')

if __name__ == '__main__':
    main()
