#ifdef __EMSCRIPTEN__

#include "online/http_request.hpp"
#include "io/file_manager.hpp"
#include "config/user_config.hpp"
#include "online/request_manager.hpp"
#include "utils/file_utils.hpp"
#include "utils/log.hpp"

#include <emscripten/fetch.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

// ============================================================================
// The browser's fetch API doesn't require global initialization like cURL
bool Online::globalHTTPRequestInit()
{
    return true;
}   // globalHTTPRequestInit

// ============================================================================
void Online::globalHTTPRequestCleanup()
{
}   // globalHTTPRequestCleanup

// ----------------------------------------------------------------------------
/** Performs the request with a synchronous emscripten_fetch. Requests are run
 *  from the request manager thread (or other worker threads), where a
 *  synchronous XMLHttpRequest is allowed. The browser handles TLS, redirects
 *  and the user agent, and a synchronous fetch reports neither progress nor
 *  can it be aborted while it is running.
 */
void Online::HTTPRequest::operation()
{
    // All parameters added have a '&' added
    if (m_parameters.size() > 0)
    {
        m_parameters.erase(m_parameters.size() - 1);
    }

    if (m_parameters.size() == 0 && !m_disable_sending_log)
    {
        Log::info("HTTPRequest", "Downloading %s", m_url.c_str());
    }
    else if (Log::getLogLevel() <= Log::LL_INFO && !m_disable_sending_log)
    {
        logMessage();
    }

    emscripten_fetch_attr_t attr;
    emscripten_fetch_attr_init(&attr);
    attr.attributes = EMSCRIPTEN_FETCH_LOAD_TO_MEMORY |
                      EMSCRIPTEN_FETCH_SYNCHRONOUS;
    attr.timeoutMSecs = 60000;

    const char* post_headers[] =
        { "Content-Type", "application/x-www-form-urlencoded", NULL };
    if (!m_download_assets_request && m_parameters.size() > 0)
    {
        strcpy(attr.requestMethod, "POST");
        attr.requestData = m_parameters.c_str();
        attr.requestDataSize = m_parameters.size();
        attr.requestHeaders = post_headers;
    }
    else
    {
        strcpy(attr.requestMethod, "GET");
    }

    // The official online services do not allow browsers (CORS); a deployment
    // may forward them through its own site, named by STK_ONLINE_PROXY.
    std::string url = m_url;
    const std::string official = "https://online.supertuxkart.net/";
    const char* proxy = getenv("STK_ONLINE_PROXY");
    if (proxy && *proxy && url.compare(0, official.size(), official) == 0)
        url = proxy + url.substr(official.size());

    m_result_code = 0;
    emscripten_fetch_t* fetch = emscripten_fetch(&attr, url.c_str());
    if (!fetch)
    {
        m_result_code = -1;
        m_error_string = "Could not start request to " + m_url;
    }
    else if (fetch->status == 0)
    {
        // Network failure, blocked by CORS, or timed out
        m_result_code = -1;
        m_error_string = "Network error (no response) for " + m_url;
    }
    else if (m_filename.size() > 0 && fetch->status >= 400)
    {
        m_result_code = fetch->status;
        m_error_string = "HTTP error " + std::to_string(fetch->status);
    }
    else if (m_filename.size() > 0)
    {
        setTotalSize((double)fetch->numBytes);
        const std::string part = m_filename + ".part";
        FILE* fout = FileUtils::fopenU8Path(part, "wb");
        if (!fout ||
            fwrite(fetch->data, 1, fetch->numBytes, fout) !=
            (size_t)fetch->numBytes)
        {
            m_result_code = -1;
            m_error_string = "Could not write to file: " + part;
        }
        if (fout)
            fclose(fout);
        if (m_result_code == 0)
        {
            if (UserConfigParams::logAddons())
                Log::info("HTTPRequest", "Download %s successfully.",
                          m_filename.c_str());
            // The behaviour of rename is unspecified if the target
            // file should already exist - so remove it.
            file_manager->removeFile(m_filename);
            if (FileUtils::renameU8Path(part, m_filename) != 0)
            {
                m_result_code = -1;
                m_error_string = "Could not rename downloaded file: " +
                                 m_filename;
            }
        }
    }
    else
    {
        setTotalSize((double)fetch->numBytes);
        m_string_buffer.assign(fetch->data, (size_t)fetch->numBytes);
    }
    if (fetch)
        emscripten_fetch_close(fetch);

    Request::operation();

    if (m_result_code != 0)
    {
        Log::error("HTTPRequest", "Request failed with error code %lld: %s",
            m_result_code, getDownloadErrorMessage());
        setProgress(-1.0f);
    }
    else
        setProgress(1.0f);
}   // operation

// ----------------------------------------------------------------------------
const char* Online::HTTPRequest::getDownloadErrorMessage() const
{
    assert(hadDownloadError());
    return m_error_string.c_str();
}   // getDownloadErrorMessage

#endif
