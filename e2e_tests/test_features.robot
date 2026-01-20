*** Settings ***
Library    SeleniumLibrary
Library    OperatingSystem

Suite Setup    Open Test Browser
Suite Teardown    Close All Browsers

*** Variables ***
${BROWSER}    chrome
${URL}        https://www.example.com

*** Test Cases ***
Test Page Load And Screenshot
    [Documentation]    Test basic page load with screenshot capture
    Go To    ${URL}
    Title Should Be    Example Domain
    Log    Page loaded successfully

Test Click And Console Logs
    [Documentation]    Test clicking elements (generates console activity)
    Go To    ${URL}
    Wait Until Page Contains    Example Domain
    Click Link    More information...
    Sleep    1s
    Log    Clicked on link

Test Form Interaction
    [Documentation]    Test form interactions on a different page
    Go To    https://www.google.com
    Sleep    1s
    Input Text    name=q    Robot Framework test
    Sleep    500ms
    Log    Form interaction complete

Test Multiple Pages Navigation
    [Documentation]    Test navigating between multiple pages
    Go To    https://www.example.com
    Sleep    500ms
    Go To    https://www.google.com
    Sleep    500ms
    Go To    https://www.example.com
    Sleep    500ms
    Log    Navigation complete

Test JavaScript Execution
    [Documentation]    Test that triggers JavaScript console logs
    Go To    https://www.example.com
    Execute JavaScript    console.log('Test log from Robot Framework');
    Execute JavaScript    console.warn('Test warning from Robot Framework');
    Execute JavaScript    console.error('Test error from Robot Framework');
    Sleep    500ms
    Log    JavaScript executed

*** Keywords ***
Open Test Browser
    ${options}=    Evaluate    sys.modules['selenium.webdriver'].ChromeOptions()    sys
    Call Method    ${options}    add_argument    --headless
    Call Method    ${options}    add_argument    --no-sandbox
    Call Method    ${options}    add_argument    --disable-dev-shm-usage
    Call Method    ${options}    add_argument    --disable-gpu
    # Enable performance logging for network capture
    ${prefs}=    Create Dictionary    performance    ALL
    Call Method    ${options}    set_capability    goog:loggingPrefs    ${prefs}
    Create Webdriver    Chrome    options=${options}
    Set Selenium Implicit Wait    5s
