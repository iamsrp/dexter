# Dexter, A Voice-Controlled Assistant

Dexter is a voice-controlled assistant, akin to Google Home, Siri and Alexa.

Dexter's your right hand!

**Table of Contents**

- [Quick start](#quick-start)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running](#running)
- [Components](#components)
  - [Inputs](#inputs)
  - [Outputs](#outputs)
  - [Services](#services)
  - [Notifiers](#notifiers)
- [Notes](#notes-and-musings)
- [Related work](#related-work)
- [Project status](#project-status)
- [Press](#press)
- [Bugs](#bugs)


## Quick start

If you quickly want to get up and running then:
 - Do a git clone of the repo: `git clone https://github.com/iamsrp/dexter`
 - Install the prerequisites: `bash dexter/requirements`
 - Make sure you have a microphone and speaker
 - Try running `dexter.py` with the appropriate config file for your distro (e.g. `env -u DISPLAY TERM=dumb ./dexter.py -c pi_config`)
 - Possibly wait for a little bit while some of the input and output components download their models for the first time

Running `bash ./requirements` will install most of what Dexter needs to function. Running `env ALL=true bash ./requirements` will install everything. Be warned that the `requirements` script installs a lot of stuff; having a (cheap) dedicated machine for running Dexter is probably wise.

The `example_config` file has a decent overview of the various services, and it's recommended that you crib from that. More documentation on the different components can be found in their modules. 


## Prerequisites

* Linux:
  - Raspberry Pi OS, on a Raspberry Pi
  - Ubuntu x86_64
* [Python 3](https://www.python.org/).
* Around 1G to 2G of free disk space (if you want to use Whisper, Coqui or Vosk with a good model).
* Most of what is listed in the `requirements` file. What you actually need will depend on what components you add.

Some of the components need extra package installed to make them work (e.g. Spotify needs various magic); this is generally documented in the module's PyDoc.


### Speech Recognition Notes

The most accurate Speech-to-Text (STT) engine is OpenAI's Whisper, but it's also the heaviest and requires mildly decent hardware in order to run at a reasonable speed. You can also run an STT engine on a remote host (e.g. using the `whisper_server.py` script) and use the `RemoteInput` class to offload the work to it.

If you want to use the [Vosk](https://alphacephei.com/vosk/) STT engine then the _Usage examples_ section on its [install page](https://alphacephei.com/vosk/install) should be enough to tell you how to install it. The various models are on its [models](https://alphacephei.com/vosk/models) page, though you will need the 64bit version of Raspberry Pi OS if you want to load in the full model, since it needs about 6Gb to instantiate. (See the Vosk install page for info on getting the 64bit `whl` file.) Per the Vosk developers, you can remove `rescore` and `rnnlm` folders from the models to make the full model run if memory is limited.

For [Coqui](https://github.com/coqui-ai/stt) you'll need the trained models and scorer from their site. For more information on setting up Coqui read their [project page](https://github.com/coqui-ai/stt) and [documentation](https://stt.readthedocs.io/en/latest/).

When it comes to audio input, make sure that you have a decent microphone with no noise; try listening to some `arecord` output to make sure it sounds clear. You can also provide a `wav_dir` argument for all of the audio input components, like `dexter.input.openai_whisper.WhisperInput`.


### Architecture Specifics

Dexter has been developed using a 4Gb Raspberry Pi 4 and a x86_64 Ubuntu machine. It's also been tested on various other hardware.

If you're running Dexter on a Raspberry Pi or the StarFive VisionFive2 then make sure that ALSA is working by testing `aplay` and `arecord`, tweaking volume and recording levels with `alsamixer`. If it is not then you may well get strange errors from `pyaudio`. You might also want a `/home/pi/.asoundrc` file, see the `dot.asoundrc` example in the top-level directory.

You can see the different hardware devices in `alsamixer`, via `F6`. You might also need to set the Audio Output in the System settings in `raspi-config` to your preference. On the StarFive board the built-in audio-out doesn't currently seem work (for me) and using a USB audio adapter seems wonky too.

For input, Coqui supports Tensorflow Light and it does a pretty decent job of recognition in near realtime. Vosk is also a more recent speech-to-text engine which seems to work well.

OpenAI's Whisper requires PyTorch to run and this is only available on the Pi 64bit OS. However it's not very fast and takes about 4x realtime to decode audio on a Pi 4; using a remote server for it is recommended.

For the StarFive VisionFive2 there's only really early Ubuntu support and most third-party libraries don't have RISC-V versions as yet. PocketSphinx seems to work as a SST engine but is very slow (10x realtime). So you probably want to run Whisper on a remote server just like you would for the Pi.

The Pi Zero 2 will also run Dexter as well but has, of course, just 512Mb of RAM. So, once again, offloading the STT engine to a server is recommended. Apart from that it looks to be fine.

The Pi also has some really great, and cheap, HATs which can be used for user feedback on status (see below). The current code supports a couple of these but adding support for new ones is pretty easy, should you be feeling keen.


## Hardware

When using a Raspberry Pi 4 to drive Dexter I've found the following work for me:
 * [Samson Go Mic Portable USB Condenser Microphone](https://www.sweetwater.com/store/detail/GoMic--samson-go-mic-portable-usb-condenser-microphone)
 * One of these is useful to tell you what it's thinking (and the Mini HATs have buttons, which can be handy):
   - [Pimoroni Unicorn HAT Mini](https://shop.pimoroni.com/products/unicorn-hat-mini)
   - [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd)
   - [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini)
 * Any old speaker!


## Configuration

The configuration for Dexter is done via a [JSON5](https://pypi.org/project/json5/) file; sorry, but it was an easy way to do it. Unlike vanilla JSON, JSON5 supports comments so the example configuration files have some associated annotation.

The file is expected to have three main dict entries: `key_phrases`, `notifiers` and `components`. The `key_phrases` are a list of strings which Dexter will listen for, in order to spot a command. For example, "Dexter, what's the time?"

The `notifiers` are ways in which Dexter let's the user know what it's currently doing (e.g. actively listening, speaking back to you, etc.).

The `components` section should be a dict with the following entries: `inputs`, `outputs` and `services`; each of these is a list of component definitions. Each component definition is a `[string,dict]` pair. The string is the fully-qualified name of the component class; the dict is a list of keyword arguments (kwargs; variable name & value pairs) which will be used to instantiate the class. The values in the kwargs may contain environment variables enclosed by dollar-sign-denoted curly braces, of the form `${VARIABLE_NAME}`.

The `test_config` file is a simple example, the platform specific ones are more fleshed out, and `example_config` is fully annotated.


## Running

You can run the client like this:

```bash
cd the_checkout_directory
nohup ./dexter.py -c test_config > dexter.log 2>&1 &
```

(If that crashes because the `DISPLAY` isn't accessible (thanks `pygame`) then add `env -u DISPLAY TERM-dumb` at the start. The `TERM=dumb` is needed since more recent versions of `pygame` seem to do nasty things with `curses` which totally borks the terminal. Hence you need to set the terminal to a dumb one, or pipe the output to a file like in the above, or both. Yuck.)

You can then stop it with a `CTRL-c` or by sending it a `SIGINT`.


## Technical Details

### Overview

The system has the following main parts:
 - Notifiers: These communicate state to the outside world
 - Components: These are the active parts of the system
   - Inputs: Get requests in
   - Outputs: Communicate responses back out
   - Services: Perform requested tasks

The system has an event loop which listens for requests using the inputs and, when one comes in, it sends the request to each of the services.

Each service will determine whether it thinks it can handle the request and, if so, creates a `Handler` instance to do so. The service then hands this handler back to the system. It also includes a belief value denoting how sure it was that the request was for it, and whether any handling should be exclusive.

The system then sorts the returned handlers according to belief and invokes the first one. If that handler was exclusive then it stops, otherwise it invokes the next, and so on.

Services can also register timer events with the event loop. This is handy for, say, setting alarms to ring at certain times. When active, services can also inform the system of their state (e.g. whether they're handling input, processing a request, performing an action, or outputting a response). The notifiers can use these status updates to inform the user of what's going on.

And that's pretty much it. Mostly, if you want to add a service then it's probably easiest to take an existing one (e.g. the `EchoService` and use it as a template). Yes, it's cargo cult programming but, at the end of the day, if it works then...


### Notifiers

The Notifiers are how Dexter tells the user what it's doing. For example, if it has started listening or if it's querying an outside service, then it uses the notifiers to say so.

There are these types right now:
 * A simple logging notifier, which writes to the console.
 * Ones for the [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd) and [Pimoroni Unicorn HAT Mini](https://shop.pimoroni.com/products/unicorn-hat-mini), which also do whirly things.
 * One for the [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini), which does pulsey things.
 * A Gnome task tray icon, which appears when Dexter is busy.


## Components

There are three types of component in the system. You may have any number of each type, but it might not be wise in certain cases (e.g. multiple audio inputs probably won't work out well). The components plug into the system to provide its various functionality. Inputs are how commands get into the system, services handle the requests, and outputs give back the service results to the user.

The PyDoc for the different components should help you get up and running with them.


### Inputs

The inputs are ways to get requests into the system. A simple **unsecured** socket-based one is provided in `test_config`, which you can telnet to and type into.

If the client is too slow at speech-to-text then you might want to consider off-loading some of the work to a machine with decent horse-power; see the `RemoteInput` class for doing that. Alternatively, the `PocketSphinxInput` class works with decent speed on a Raspberry Pi, but its accuracy isn't great.

It is recommended that you have only a single audio input. The reason for this is left as an exercise for the reader.

There are other simple input types mostly for physical interaction:
 * MediaKeyInput: This binds certain phrases to the media keys (Play, Stop, Next Track, Previous Track)
 * GPIO: Which binds certain phrases to the buttons on some HATs


### Outputs

These are ways to get Dexter's responses back to the user. These currently:
 * Speech-to-text via engines like [Mimic3](https://mycroft-ai.gitbook.io/docs/mycroft-technologies/mimic-tts/mimic-3/), [Festival](http://www.cstr.ed.ac.uk/projects/festival/) or [ESpeak](http://espeak.sourceforge.net/).
 * Text output via the `LogOutput` or Ubuntu desktop notifiers.
 * Transmission to an unsecured remote socket.


### Services

The services are what actually handle the user requests. These might be things like playing music, telling you what the weather is, or setting some sort of timer. A simple `EchoService` is a basic example, and just says back to you what you said to it (quelle surprise!).

A quick overview of the current set of service modules is:
 * Bespoke: Canned responses to certain phrases.
 * Chronos: Services to do with time (timers etc.).
 * Developer: Simple services to help with Dexter development work.
 * Fortune: Pulls fortunes out of BSD Fortune files.
 * Language: Looking up words in a dictionary, spelling.
 * Life: The day-to-day of things.
 * Numeric: Simple mathematic functions.
 * Music & Spotify: Play music from local disk, Spotify, etc.
 * PurpleAir: Look up stats from the [Purple Air](https://purpleair.com/) air sensors.
 * Randomness: Various random generators.
 * TPLink Kasa: Control the TP Link Kasa IOT plugs and lightbulbs.
 * UPnP: Services which employ UPnP.
 * Volume: Sound control.
 * Weather: Get the weather (US or UK only).
 * WikiQuery: Look up things on (surpise!) Wikipedia.


## Notes and Musings

Dexter is an attempt to create a home assistant, akin to Google Home, Siri or Alexa, but without reliance on connecting to a proprietary cloud service to do the heavy lifting. It was originally designed to work on a Raspberry Pi running the standard Raspberry Pi OS (both 32bit and 64bit versions), but also works on x86-64 Ubuntu.

Writing components for Dexter should, in theory, be simple and intuitive. Most of the time you'll probably wind up writing services for it, though other types of notifier might be handy too. I generally find that you can get a beta version of something up and running in an hour or so. Of course, you then spend three more hours fiddling with it in various ways; that is probably the way of *most* coding projects though.

When it comes to getting Dexter working "right" the main thing I wind up doing is getting the sound quality good on the audio input. Some microphones are impressively bad and it's amazing that speech-to-text works at all with what they produce. So if you're having trouble, try setting the `wav_dir` argument of the audio input (e.g. to be `/tmp`) and listen to what it's getting. It will create files of the form `1604895798.wav`, where the number is seconds-since-epoch. You can then fiddle with the microphone settings (or use different microphones) until you get something which sounds okay.

It's far from perfect, and you may have to ask it to do something three times, but it's still kind of amazing that you can do all this on a $35 computer..! (Oh, with a $50 microphone, $15 HAT, $20 speaker, ...)


## Related work

Of course, Dexter isn't the only implementation of this idea. Other ones out there are:
 * [Jasper](https://jasperproject.github.io/)
 * [Leon](https://github.com/leon-ai/leon)
 * [Mycroft](https://mycroft.ai/)
 * [Project Alice](https://github.com/project-alice-assistant/ProjectAlice)
 * [Rhasspy](https://github.com/rhasspy/rhasspy)
 * [SEPIA](https://sepia-framework.github.io/)

How is Dexter different? Well, that's in the eye of the beholder really. The basic idea is the same, and they all have support for adding services (or equivalent) on your own. Of course, I can say without a hint of bias, that Dexter is the most awesome-est of the bunch. Like, I mean, dude: you can make it do swirly things with lights when it's listening to you or doing work. Who could ask for more?!


## Project status

Right now Dexter is at the point where it does pretty much what I wanted it to and so most of the work happening on it is related to bug fixes and tweaks, as opposed to adding new features. I'll also be keeping it ticking over with the updates to underlying libraries etc. so that it still works out of the box.

The open source release of OpenAI's Whisper STT engine in July 2022 (thank you!) breathed new life into this project and spurred a small flurry of development wor. Since they I added a bunch of features which I (and my "beta testers") wanted. I also took the opportunity to get it going on a refurbished [Dell OptiPlex 7050 Micro](https://duckduckgo.com/?t=ffsb&q=Dell+OptiPlex+7050+Micro+Core+i5+2.7+GHz+&ia=web) running Ubuntu.


## Press

Shameless self-promotion on HN: https://news.ycombinator.com/item?id=25718392


## Bugs

At some point it should be fixed to use `setup.py` to install itself.

If you are running with an inaccessible `DISPLAY` then you might see pygame do this:
```
Fatal Python error: (pygame parachute) Segmentation Fault
```
If that's the case, then simply unset the `DISPLAY` when running, e.g. with `env -u DISPLAY ./dexter.py -c config`. However, if the `DISPLAY` is not set then pygame may attempt to set up `curses` instead and this renders the terminal unusable. To avoid this  it's suggested that you set `TERM=dumb`:
```
env -u DISPLAY TERM=dumb ./dexter.py -c config
```
or redirect the output to a file:
```
env -u DISPLAY ./dexter.py -c config > dexter.log 2>&1
```
or both. Lovely.

The speech recognition could do with some work:
 * Not perfect at detecting the start and end of speech
 * It would be better if it continuously listened and picked up instructions as it went along

Some of the underlying libraries can hit fatal errors, causing the whole thing to `abort()` and die.

PyFestival seems to yield a `aplay: main:831: audio open error: Device or resource busy` error on the StarFive VisionFive 2, meaning you get nothing out.

Spotify seems to drop the connection to its clients if they are idle for too long.

The PyDictionary package doesn't seem to install properly right now (20230301).

Ubuntu 22.10 uses Pipewire as the new audio subsystem. However, this seems to break ALSA, and PyAudio uses ALSA under the hood. You can remove it with `sudo dpkg -r pipewire`, which causes Ubuntu to revert back to using PulseAudio.
