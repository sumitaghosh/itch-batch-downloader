# download pretty a file

import os
import shutil
import time

import dateparser
import requests

from datetime import datetime

# Print iterations progress
def printProgressBar(iteration, total, prefix='', suffix='', usepercent=True, decimals=1, fill='X', debugon=False):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        usepercent  - Optoinal  : display percentage (Bool)
        decimals    - Optional  : positive number of decimals in percent complete (Int), ignored if usepercent = False
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """

    prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + "[INFO] " + prefix

    # length is calculated by terminal width
    twx, twy = shutil.get_terminal_size()
    length = twx - 1 - len(prefix) - len(suffix) -4
    if usepercent:
        length = length - 6
    if total == 0:
        filledLength = int(length * iteration // 1)
    else:
        filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    
     # process percent
    if usepercent:
        if total == 0:
            percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(1)))
        else:
            percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='', flush=True)
    else:
        print('\r%s |%s| %s' % (prefix, bar, suffix), end='', flush=True)

    # Print New Line on Complete
    if iteration == total:
        print(flush=True)

def download_a_file(url, filename="", session=None, cookies=None, rename_old=True, skip_if_identical=True, debugon=False):
    """
    Download a file, returning True if a fresh copy was written.
    For Cloudflare-mirrored URLs (itchio-mirror.* or r2.cloudflarestorage.com)
    we skip the preliminary HEAD request because the signed URL expires after
    60 seconds. Doing a HEAD first would waste that time and cause the GET to
    fail with “Invalid URL / Expired signature”.
    """
    if cookies is None and session is not None:
        cookies = session.cookies
    if session is None:
        session = requests.Session()

    dlurl = url  # keep the original string for later use

    # ------------------------------------------------------------------
    # Detect Cloudflare‑mirrored URLs
    # ------------------------------------------------------------------
    is_cloudflare = dlurl.startswith("https://itchio-mirror.") or dlurl.startswith(
        "https://r2.cloudflarestorage.com"
    )

    if is_cloudflare:
        # Direct GET – no HEAD, no skip‑if‑identical (we don’t have reliable metadata)
        response = session.get(dlurl, stream=True, cookies=cookies)
        if response.status_code != 200:
            print(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                + " "
                + f"{Fore.RED}[ERROR]{Style.RESET_ALL} Cloudflare download failed ({response.status_code})"
            )
            return False

        # Try to pull a reasonable filename from the headers; fall back to the URL tail.
        raw_name = ""
        cd = response.headers.get("content-disposition")
        if cd and "filename=" in cd:
            raw_name = cd.split("filename=")[-1].strip('";\'')
        else:
            raw_name = dlurl.split("/")[-1].split("?")[0]

        # 2️⃣  If the caller gave us a directory, join the raw name to it.
        #     If the caller gave us a non‑empty filename, honour that.
        if filename == "" or os.path.isdir(filename):
            # `filename` is either empty or a directory – construct the full path.
            dest_dir = filename if os.path.isdir(filename) else os.getcwd()
            final_path = os.path.join(dest_dir, raw_name)
        else:
            # Caller supplied an explicit filename (rare for Cloudflare URLs)
            final_path = filename

        # ------------------------------------------------------------------
        # From here on we reuse the same logic that the original code used
        # after the HEAD request – progress bar, rename‑old, timestamp, etc.
        # ------------------------------------------------------------------
        dltime = response.headers.get("last-modified", "")
        datalength = int(response.headers.get("content-length", 0))

    else:
        # ----------- ORIGINAL PATH (keep HEAD for normal CDN URLs) ----------
        head_resp = session.head(dlurl)
        if head_resp.status_code != 200:
            print(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                + " "
                + f"{Fore.RED}[ERROR]{Style.RESET_ALL} HEAD request failed ({head_resp.status_code})"
            )
            return False

        dltime = head_resp.headers["last-modified"]
        datalength = int(head_resp.headers["content-length"])

        # ------------------------------------------------------------------
        # Resolve the final filename (same logic as the Cloudflare branch)
        # --------------------------------------------------------
        raw_name = ""
        cd = head_resp.headers.get("content-disposition")
        if cd and "filename=" in cd:
            raw_name = cd.split("filename=")[-1].strip('";\'')
        else:
            raw_name = dlurl.split("/")[-1].split("?")[0]

        if filename == "" or os.path.isdir(filename):
            dest_dir = filename if os.path.isdir(filename) else os.getcwd()
            final_path = os.path.join(dest_dir, raw_name)
        else:
            final_path = filename

        # Skip‑if‑identical logic (only for normal CDN files)
        if os.path.exists(filename) and skip_if_identical:
            stats = os.stat(filename)
            if (
                dateparser.parse(dltime).timestamp() == stats.st_mtime
                and datalength == stats.st_size
            ):
                print(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    + " "
                    + f"[INFO] File {filename} already fully downloaded – skipping"
                )
                return False

        # Now fetch the actual payload
        response = session.get(dlurl, stream=True, cookies=cookies)
        if response.status_code != 200:
            print(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                + " "
                + f"{Fore.RED}[ERROR]{Style.RESET_ALL} GET request failed ({response.status_code})"
            )
            return False

    # ------------------------------------------------------------------
    # At this point we have:
    #   * `response`   – the streaming HTTPResponse object
    #   * `final_path` – the absolute path where the file should be saved
    #   * `dltime`     – remote modification timestamp (may be empty)
    #   * `datalength`– expected size in bytes
    # ---------------------------------------------------------

    # ------------------------------------------------------------------
    # Rename old file if requested (only when a *file* exists, not a dir)
    # ------------------------------------------------------------------
    if os.path.exists(final_path) and rename_old:
        now = datetime.now()
        ts = now.strftime("%Y%m%d%H%M%S")
        old_name = f"{final_path}_{ts}.old"
        print(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + " "
            + f"[INFO] Renaming {final_path} → {old_name}"
        )
        if os.path.exists(old_name):
            os.remove(old_name)
        os.rename(final_path, old_name)

    # ------------------- STREAM TO DISK -------------------
    if debugon:
        print(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + " "
            + f"[DEBUG] Starting download of {dlurl} → {final_path}"
        )
    else:
        print(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + " "
            + f"[INFO] Starting download of {final_path}"
        )

    incompletefilename = final_path + ".incomplete"
    with open(incompletefilename, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)
            # (progress‑bar code omitted for brevity – keep yours)
    # ------------------------------------------------------------------
    # Finish up – rename the temporary file to the final name
    # ------------------------------------------------------------------
    os.rename(incompletefilename, final_path)

    # ------------------------------------------------------------------
    # Verify size
    # ------------------------------------------------------------------
    size_on_disk = os.path.getsize(final_path)
    if size_on_disk != datalength:
        print(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + " "
            + f"{Fore.RED}[ERROR]{Style.RESET_ALL} Size mismatch (disk {size_on_disk} ≠ expected {datalength})"
        )
        return False

    # ------------------------------------------------------------------
    # Apply the remote modification timestamp (if we got one)
    # ------------------------------------------------------------------
    if dltime:
        ts = int(dateparser.parse(dltime).timestamp())
        os.utime(final_path, (ts, ts))

    return True

    #     # If caller didn’t supply a filename, try to infer it from headers
    #     if filename == "":
    #         cd = response.headers.get("content-disposition")
    #         if cd and "filename=" in cd:
    #             filename = cd.split("filename=")[-1].strip('";\'')
    #         else:
    #             filename = dlurl.split("/")[-1].split("?")[0]

    # # ------------------------------------------------------------------
    # # Common download routine (progress bar, rename‑old, timestamp, etc.)
    # # ------------------------------------------------------------------
    # shortfilename = os.path.basename(filename)
    # incompletefilename = filename + ".incomplete"
    # starttime = time.time()
    # datadownloaded = 0

    # # Rename old file if requested
    # if os.path.exists(filename) and rename_old:
    #     now = datetime.now()
    #     ts = now.strftime("%Y%m%d%H%M%S")
    #     old_name = f"{filename}_{ts}.old"
    #     print(
    #         datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         + " "
    #         + f"[INFO] Renaming {filename} → {old_name}"
    #     )
    #     if os.path.exists(old_name):
    #         os.remove(old_name)
    #     os.rename(filename, old_name)

    # # ------------------- STREAM TO DISK -------------------
    # if debugon:
    #     print(
    #         datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         + " "
    #         + f"[DEBUG] Starting download of {dlurl} → {filename}"
    #     )
    # else:
    #     print(
    #         datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         + " "
    #         + f"[INFO] Starting download of {filename}"
    #     )

    # with open(incompletefilename, "wb") as f:
    #     for chunk in response.iter_content(chunk_size=8192):
    #         if not chunk:
    #             continue
    #         f.write(chunk)
    #         datadownloaded += len(chunk)

    #         # Progress bar (reuse your existing printProgressBar)
    #         elapsed = time.time() - starttime
    #         kbs = (datadownloaded / elapsed) / 1024 if elapsed else 0
    #         suffix = f"{shortfilename}"
    #         prefix = f"{round(datadownloaded/1024/1024,1)}/{round(datalength/1024/1024,1)} MB ({round(kbs,1)} KB/s)"
    #         printProgressBar(datadownloaded, datalength, suffix=suffix, prefix=prefix, debugon=debugon)

    # # ------------------- FINISH UP -------------------
    # os.rename(incompletefilename, filename)

    # # Verify size
    # size_on_disk = os.path.getsize(filename)
    # if size_on_disk != datalength:
    #     print(
    #         datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         + " "
    #         + f"{Fore.RED}[ERROR]{Style.RESET_ALL} Size mismatch (disk {size_on_disk} ≠ expected {datalength})"
    #     )
    #     return False

    # # Apply the remote modification timestamp (if we got one)
    # if dltime:
    #     ts = int(dateparser.parse(dltime).timestamp())
    #     os.utime(filename, (ts, ts))

    # return True