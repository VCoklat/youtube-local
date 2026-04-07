# youtube-local

> **Author's Note / Fork Information**
> 
> Welcome! This is my first Free and Open Source Software (FOSS) repository that I am sharing publicly. This is a modified fork, and I highly encourage you to visit and support the original repository as well!
> 
> **My Motivation:** In my country, mobile data prices are high and there is strict internet censorship. I needed a lightweight server proxy to help me lower my data usage that I could combine with mesh VPNs like Tailscale or ZeroTier. I also prefer using Windows, and I found that most other solutions require Docker, which can be heavy and hard to configure. So, I decided to modify this project to fit my needs!
> 
> **What I've Added:** To save bandwidth, I've added a **compression feature** and built a **barebone Reddit client** (`Reddit-local`) directly into the proxy. 
> 
> **Future Plans:** I am looking to expand this project to support TikTok, Facebook, Instagram, and other websites in the future.
> 
> **Looking for Opportunities:** I am currently looking for a job! I would prefer to relocate to Singapore or find a remote working position. If you have any opportunities, please feel free to DM me personally.
> 
> **Credits & Community:** Huge thanks to the original creators of `youtube-local`, the developers of all the similar projects listed at the bottom, and the open-source community. I also used AI to help me build and document parts of this project. Feel free to fork my project, open issues, or give suggestions!

---

![screenshot](https://user-images.githubusercontent.com/28744867/64483429-8a890780-d1b6-11e9-8423-6956ff7c588d.png)
youtube-local is a browser-based client written in Python for watching Youtube anonymously and without the lag of the slow page used by Youtube. One of the primary features is that all requests are routed through Tor or through a local proxy.

The Youtube API is not used, so no keys or anything are needed. It uses the same requests as the Youtube webpage.

## Screenshots
[Gray theme](https://user-images.githubusercontent.com/28744867/64483431-8e1c8e80-d1b6-11e9-999c-14d36ddd582f.png)

[Dark theme](https://user-images.githubusercontent.com/28744867/64483432-8fe65200-d1b6-11e9-90bd-32869542e32e.png)

[Non-Theater mode](https://user-images.githubusercontent.com/28744867/64483433-92e14280-d1b6-11e9-9b56-2ef5d64c372f.png)

[Channel](https://user-images.githubusercontent.com/28744867/64483436-95dc3300-d1b6-11e9-8efc-b19b1f1f3bcf.png)

[Downloads](https://user-images.githubusercontent.com/28744867/64483437-a2608b80-d1b6-11e9-9e5a-4114391b7304.png)

## Features
* Standard pages of Youtube: search, channels, playlists
* Anonymity from Google's tracking by routing requests through Tor
* Local playlists: These solve the two problems with creating playlists on Youtube: (1) they're datamined and (2) videos frequently get deleted by Youtube and lost from the playlist, making it very hard to remember what was deleted.
* Themes: Light, Gray, and Dark
* Subtitles
* Easily download videos or their audio
* No ads
* View comments
* Javascript not required
* Theater and non-theater mode
* Subscriptions that are independent from Youtube
  * Can import subscriptions from Youtube
  * Works by checking channels individually
  * Can be set to automatically check channels.
  * For efficiency of requests, frequency of checking is based on how quickly channel posts videos
  * Can mute channels, so as to have a way to "soft" unsubscribe. Muted channels won't be checked automatically or when using the "Check all" button. Videos from these channels will be hidden.
  * Can tag subscriptions to organize them or check specific tags
* Fast page
  * No distracting/slow layout rearrangement
  * No lazy-loading of comments; they are ready instantly.
* Settings allow fine-tuned control over when/how comments or related videos are shown:
  1. Shown by default, with click to hide
  2. Hidden by default, with click to show
  3. Never shown
* Optionally skip sponsored segments using [SponsorBlock](https://github.com/ajayyy/SponsorBlock)'s API
* Custom video speeds
* Video transcript
* Supports all available video qualities: 144p through 2160p

## Reddit-local (read-only)

This project now includes a lightweight Reddit-local mode focused on privacy and performance.
![screenshot home]("image/home.png")
![screenshot reddit home]("image/reddithome.png")
![screenshot subreddit]("image/subreddit.png")

### Routes
- Home feed: `http://localhost:8080/reddit` (`r/popular`)
- Alternate home feed: `http://localhost:8080/reddit?source=all`
- Subreddit: `http://localhost:8080/reddit/r/<subreddit>`
- Post + comments: `http://localhost:8080/reddit/r/<subreddit>/comments/<post_id>/<slug>`
- Search: `http://localhost:8080/reddit/search?q=<query>`
- User history: `http://localhost:8080/reddit/user/<username>`

### API routes (read-only)
- `GET /api/home`
- `GET /api/r/<subreddit>`
- `GET /api/post/<post_id>?subreddit=<subreddit>`
- `GET /api/post/r/<subreddit>/comments/<post_id>/<slug>`
- `GET /api/search?q=<query>&kind=posts|subreddits`
- `GET /api/user/<username>?kind=all|submitted|comments`

### Privacy behavior
- Reddit JSON endpoints are fetched with a custom User-Agent: `reddit-local/1.0 (+https://github.com/VCoklat/youtube-local)`.
- Supported Reddit media hosts are proxied via backend route `/reddit/media`.
- Direct third-party media links are not embedded in Reddit-local templates; rendered media uses proxied URLs.
- Outbound URLs are sanitized to strip tracking parameters such as `utm_*`, `ref`, and related fields.

### Compression features
- `compress_images` (network setting, default `False`)
  - Recompresses proxied JPEG/PNG images to reduce bandwidth.
  - Applies to standard proxied image hosts and Reddit media proxy route (`/reddit/media`).
  - Only applies to full-image responses (not `Range` requests), and requires Pillow.
- `image_quality` (network setting, default `70`)
  - JPEG quality used when `compress_images` is enabled (`1-100`).
- `enable_response_compression` (network setting, default `False`)
  - Gzip-compresses eligible text responses (HTML/CSS/JS/JSON/XML/plain text) when the browser sends `Accept-Encoding: gzip`.
  - This includes Reddit-local pages and Reddit API responses served by this app.

### Scope and non-goals
- Reddit-local is intentionally read-only.
- No Reddit account login, voting, posting, or commenting flows are implemented.
- No realtime notifications/chat and no algorithmic personalization features are added.

## Planned features
- [ ] Support for more sites, such as Facebook, instagram, tiktok, etc.

## Installing

### Windows

Download the zip file under the Releases page. Unzip it anywhere you choose.

### Linux/MacOS

Download the tarball under the Releases page and extract it. `cd` into the directory and run
```
pip3 install -r requirements.txt
```

**Note**: If pip isn't installed, first try installing it from your package manager. Make sure you install pip for python 3. For example, the package you need on debian is python3-pip rather than python-pip.


### FreeBSD

If pip isn't installed, first try installing it from the package manager:
```
pkg install py39-pip
```

Some packages are unable to compile with pip, install them manually: 
```
pkg install py39-gevent py39-sqlite3
```

Download the tarball under the Releases page and extract it. `cd` into the directory and run
```
pip install -r requirements.txt
```

**Note**: You may have to start the server redirecting its output to /dev/null to avoid I/O errors: 
```
python3 ./server.py > /dev/null 2>&1 &
```

## Usage

To run the program on windows, open `run.bat`. On Linux/MacOS, run `python3 server.py`.

**Note for Mac users**: If you installed Python from the installer on python.org, you will need to have run the file `Install Certificates.command` in the directory `Applications/Python 3.x` where you installed it, otherwise the requests to Youtube might fail due to SSL errors.

To run it at startup on Windows, right click `run.bat` and click "Create Shortcut." Then, move the shortcut to the Startup folder. You can access the Startup folder by pressing `Windows Key + R` and typing `shell:startup`.


Access youtube URLs by prefixing them with `http://localhost:8080/`, For instance, `http://localhost:8080/https://www.youtube.com/watch?v=vBgulDeV2RU`
You can use an addon such as Redirector ([Firefox](https://addons.mozilla.org/en-US/firefox/addon/redirector/)|[Chrome](https://chrome.google.com/webstore/detail/redirector/ocgpenflpmgnfapjedencacbgkme)) with a rule like `^(https?://(?:www\.)?youtube\.com/.*)` -> `http://localhost:8080/$1` to be automatically redirected to youtube-local.

If you want embeds on the web to also redirect to youtube-local, make sure "Iframes" is checked under advanced options in your redirector rule.

youtube-local can be added as a search engine in firefox to make searching more convenient. See [here](https://support.mozilla.org/en-US/kb/add-or-remove-search-engine-firefox) for information on how to add a custom search engine.

### Portable mode

If you wish to run this in portable mode, create the empty file "settings.txt" in the program's main directory. If the file is there, settings and data will be stored in the same directory as the program. Otherwise, settings and data are stored in a folder called `youtube-local` in `%APPDATA%` on Windows and `~/.config` on Linux/Mac.

### Using Tor

In the settings page, set "Route Tor" to "On, except video" (the second option). Be sure to save the settings.

Ensure Tor is listening for Socks5 connections on port 9150. A simple way to accomplish this is by opening the Tor Browser Bundle and leaving it open. However, you will not be accessing the program from Tor Browser. You can access youtube-local from your regular browser. Tor browser merely needs to be open to allow youtube-local to route its requests through it.

### Standalone Tor

If you don't want to waste system resources leaving the Tor Browser open in addition to your regular browser, you can configure standalone Tor to run instead using the following instructions.

For Windows, to make standalone Tor run at startup, press Windows Key + R and type `shell:startup` to open the Startup folder. Create a new shortcut there. For the command of the shortcut, enter `"C:\path\to\Tor Browser\Browser\TorBrowser\Tor\tor.exe"`. Tor will run in the background.

For Debian/Ubuntu, you can `sudo apt install tor` to install the command line version of Tor, and then run `sudo systemctl start tor` to run it as a background service that will get started during boot. You'll need to change the Tor port to `9050` on youtube-local settings.

### Tor video routing

If you wish to route the video through Tor, set "Route Tor" to "On, including video". Because this is bandwidth-intensive, you are strongly encouraged to donate to the [consortium of Tor node operators](https://donate.torproject.org/).

In general, Tor video routing will be slower (for instance, moving around in the video is quite slow). I've never seen any signs that watch history in youtube-local affects on-site Youtube recommendations, so this feature isn't really needed anyway.

### Importing subscriptions

1. Go to the [Google takeout manager](https://takeout.google.com/takeout/custom/youtube).
2. Log in if asked.
3. Click on "All data included", then on "Deselect all", then select only "subscriptions" and click "OK".
4. Click on "Next step" and then on "Create export".
5. Click on the "Download" button after it appears.
6. From the downloaded takeout zip extract the .csv file. It is usually located under `YouTube and YouTube Music/subscriptions/subscriptions.csv`
7. Go to the subscriptions manager in youtube-local. In the import area, select your .csv file, then press import.

Supported subscriptions import formats:
- NewPipe subscriptions export JSON
- Google Takeout CSV
- Old Google Takeout JSON
- OPML format from now-removed YouTube subscriptions manager

## Contributing

Pull requests and issues are welcome

For coding guidelines and an overview of the software architecture, see the HACKING.md file.

## License

This project is licensed under the GNU Affero General Public License v3 (GNU AGPLv3) or any later version.

Permission is hereby granted to the youtube-dl project at [https://github.com/ytdl-org/youtube-dl](https://github.com/ytdl-org/youtube-dl) to relicense any portion of this software under the Unlicense.


## Similar projects
- [youtube-local](https://github.com/user234683/youtube-local), which this project based off
- [invidious](https://github.com/iv-org/invidious) Similar to this project, but also allows it to be hosted as a server to serve many users
- [Yotter](https://github.com/ytorg/Yotter) Similar to this project and to invidious. Also supports Twitter
- [FreeTube](https://github.com/FreeTubeApp/FreeTube) (Similar to this project, but is an electron app outside the browser)
- [yt-local](https://git.sr.ht/~heckyel/yt-local) Fork of this project with a different page design
- [NewPipe](https://newpipe.schabi.org/) (app for android)
- [mps-youtube](https://github.com/mps-youtube/mps-youtube) (terminal-only program)
- [youtube-viewer](https://github.com/trizen/youtube-viewer)
- [smtube](https://www.smtube.org/)
- [Minitube](https://flavio.tordini.org/minitube), [github here](https://github.com/flaviotordini/minitube)
- [toogles](https://github.com/mikecrittenden/toogles) (only embeds videos, doesn't use mp4)
- [youtube-dl](https://rg3.github.io/youtube-dl/), main plugin for this website