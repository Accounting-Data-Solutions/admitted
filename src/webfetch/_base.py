from __future__ import annotations
import logging
import time
from typing import Callable
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from .element import Element
from .exceptions import NavigationError
from ._locator import find_any, match_url
from ._manager import ChromeManager
from ._outside import outside_request
from ._window import Window

logger = logging.getLogger(__name__)


class BasePage:
    """Represents a page on a web site."""

    def __init__(self, browser: ChromeManager, retries: int = 3, debug: bool = False):
        """Initialize common class attributes

        Args:
          browser: ChromeManager instance representing Chrome window.
          retries: Number of times the `navigate` method should try to open the requested URL.
          debug: If True, will output chromedriver.log on the desktop and suppress retries.
        """
        self.browser = browser
        self.window = Window(self.browser)
        self.outside_request = outside_request
        self.retries = 0 if debug else retries

    def css(
        self,
        selector: str,
        multiple: bool = False,
        mapping: dict[str, str] | None = None,
    ) -> Element | list[Element]:
        """Return the element with the given CSS selector.

        Args:
          selector: The css selector identifying the element.
          multiple: If true, return a list of all matching elements.
          mapping: If set, will be used to expand template values in selector.

        Returns:
          An Element object of the discovered element.

        Raises:
          TimeoutException: No element matching the specified selector was found.
        """
        return find_any(self.browser, By.CSS_SELECTOR, selector, multiple, mapping)

    def xpath(
        self,
        path: str,
        multiple: bool = False,
        mapping: dict[str, str] | None = None,
    ) -> Element | list[Element]:
        """Return the element with the given XPath.

        Args:
          path: The XPath identifying the element.
          multiple: If true, return a list of all matching elements.
          mapping: If set, will be used to expand template values in path.

        Returns:
          An Element object of the discovered element.

        Raises:
          TimeoutException: No element matching the specified XPath was found.
        """
        return find_any(self.browser, By.XPATH, path, multiple, mapping)

    def switch_id(self, options: dict[str, Callable[[Element], Element]]) -> Element:
        """Wait for any of several elements to become available and return the first one found.

        Args:
          options: Dictionary where keys are element IDs to watch for and values are the callback for when
            that key is found.

        Returns:
          The return value from the callback, which should be the discovered WebElement.

        Raises:
          TimeoutException: No element with one of the specified IDs was found within the allotted time.
        """
        ids = options.keys()
        element = find_any(self.browser, By.CSS_SELECTOR, ", ".join([f'[id="{id_}"]' for id_ in ids]), False, None)
        found = element.get_property("id")
        return options[found](element)

    @property
    def current_url(self):
        """Return the current URL that Chrome is on."""
        return self.browser.current_url

    def _navigate(
        self,
        url: str,
        callback: Callable[[], bool] | None = None,
        retry_wait: int = 10,
        retries_override: int | None = None,
        enforce_url: bool = False,
    ) -> None:
        """Navigate Chrome to the specified URL, retrying with exponential back-off.

        Args:
          url: The URL to navigate to.
          callback: Function to call before pause and retry, return True if navigation complete.
          retry_wait: Number of seconds to wait for first retry if initial get fails.
          retries_override: Number of times to attempt get, if other than instance default required.
          enforce_url: Consider it an error if current_url != url after navigation.
        """
        retries = self.retries if retries_override is None else retries_override
        retry = 0
        last_exception = None
        while True:
            try:
                self.browser.get(url)
                success = True
            except WebDriverException as exc:
                logger.debug(f"Error on try {retry}: {exc}.")
                last_exception = exc
                success = False
            # if we got where we were going, we're done!
            if enforce_url and not match_url(self.current_url, url):
                success = False
            # if we've exhausted retries, raise the error
            if not success and retry >= retries:
                raise NavigationError(f"Failed after {retry + 1} tries navigating to {url}.") from last_exception
            # check if callback signals exit
            if callback is not None:
                success = success and callback()
            if success:
                break
            retry += 1
            pause = retry_wait * (retry**2)
            time.sleep(pause)
