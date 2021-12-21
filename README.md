# Dexter, A Voice Controlled Assistant

Dexter is a voice controlled assistant, akin to Google Home and Alexa. Dexter's your right hand (in theory).

Originally developed for Raspberry Pi OS, it also works on Ubuntu.

This is very much a toy project and should be considered work in progress. That being said, it kinda works for me; it might for you too.

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
- [Bugs](#bugs)

## Quick start

If you quickly want to get up and running then:
 - Do a git clone of the repo
 - Install the prerequisites
 - Make sure that the appropriate model etc. files are where the config file is looking for them
 - Make sure you have a microphone and speaker
 - Try running dexter.py with the appropriate config file for your distro (either `pi_config` or `ubunutu_config`)
You will then be hugely underwhelmed, but at least the basic functionality should be there at this point.

## Prerequisites

* Linux:
  - Raspberry Pi OS (on a Raspberry Pi)
  - Ubuntu (on an x64-86 box)
* [Python 3](https://www.python.org/).
* Around 1G to 2G of free disk space, if you want to use DeepSpeech or Vosk with a good model.
* Most of what is listed in the `requirements` file. What you actually need will depend on what components you add.

If you want to use [Vosk](https://alphacephei.com/vosk/) for speech-to-text then the _Usage examples_ section on its [install page](https://alphacephei.com/vosk/install) should be enough to tell you how to install it. The various models are on its [models](https://alphacephei.com/vosk/models) page, though I have had trouble getting the full model to run on a 8Gb Raspbery Pi 4.

You'll also need the trained models and scorer from [DeepSpeech](https://github.com/mozilla/DeepSpeech). For more information on setting up DeepSpeech read their [project page](https://github.com/mozilla/DeepSpeech) and [documentation](https://deepspeech.readthedocs.io/).

Some of the components need extra package installed to make them work (e.g. Spotify needs various magic); this is generally documented in the module's PyDoc.

When it comes to recording, make sure that you have a decent microphone with no noise; try listening to some `arecord` output to make sure it sounds clear. You can also provide a `wav_dir` argument for some of the audio input components, like `dexter.input.deepspeech.DeepSpeechInput`.

### Raspberry Pi Specifics

Dexter has been tested and developed using, most recently a 2Gb Raspberry Pi 4.

If you're running Dexter on a Raspberry Pi then make sure that ALSA is working by testing `aplay` and `arecord`, tweaking volume and recording levels with `alsamixer`. If it is not then you may well get strange errors from `pyaudio`. You might also want a `/home/pi/.asoundrc` file which looks something like this:
   ```
pcm.!default {
        type asym
        playback.pcm {
                type plug
                slave.pcm "hw:0,0"
        }
        capture.pcm {
                type plug
                slave.pcm "hw:1,0"
        }
}
```
You can see the different hardware devices in `alsamixer`, via F6. You might also need to set the Audio Output in the System settings in `raspi-config` to your preference.

For input, DeepSpeech 0.9.0 onwards supports Tensorflow Light and it does a pretty decent job of recognition in near realtime. Vosk is also a more recent speech-to-text engine which seems to work well.

The Pi also has some really great, and cheap, HATs which can be used for user feedback on status (see below). The current code supports a couple of these but adding support for new ones is pretty easy, should you be feeling keen.

## Configuration

The configuration for Dexter is done via a [JSON](https://json.org/) file; sorry, but it was an easy way to do it. I guess I could have made it a Python file which you comment out bits of but that seemed more icky. Of course, JSON doesn't support comments so the default config files are not annotated.

The file is expected to have three main dict entries: `key_phrases`, `notifiers` and `components`. The `key_phrases` are a list of strings which Dexter will listen for, in order to spot a command. For example, "Dexter, what's the time?"

The `notifiers` are ways in which Dexter let's the user know what it's currently doing (e.g. actively listening, speaking back to you, etc.).

The `components` should be a dict with the following entires: `inputs`, `outputs` and `services`; each of these is a list of component definitions. Each component definition is a `[string,dict]` pair. The string is the fully-qualified name of the component class; the dict is a list of keyword arguments (kwargs; variable name & value pairs) which will be used to instantiate the class. The values in the kwargs may contain environment variables enclosed by dollar-sign-denoted curly braces, of the form `${VARIABLE_NAME}`.

See the `test_config` file as a simple example, and the platform specific ones which are more fleshed out.

## Running

You can run the client like this:

```bash
cd the_checkout_directory
./dexter.py -c test_config
```

You can then stop it with a `CTRL-c` or by sending it a `SIGINT`.

### Notifiers

The Notifiers are how Dexter tells the user what it's doing. For example, if it has started listening or if it's querying an outside service, then it will effectively say so via simple means.

There are at least these right now:
 * A simple logging notifier, which writes to the console.
 * Ones for the [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd) and [Pimoroni Unicorn HAT Mini](https://shop.pimoroni.com/products/unicorn-hat-mini), which also do whirly things.
 * One for the [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini), which does pulsey things.
 * A Gnome task tray icon, which appears when Dexter is busy.

## Components

There are three types of component in the system. You may have any number of each type, but it might not be wise in certain cases (e.g. multiple audio inputs probably won't work out well). The components plug into the system to provide its various functionality. Inputs are how commands get into the system, services handle the commands, and outputs give back the service results to the user.

The PyDoc for the different components should help you get up and running with them.

### Inputs

The inputs are ways to get requests into the system. A simple **unsecured** socket-based one is provided in `test_config`, which you can telnet to and type into.

Inputs which convert spoken audio into text are also provided. The `DeepSpeechInput` class has great accuracy but be sure to be using the versions which use TensorFlowLite (0.9.0 and up), since the prior versions are super slow. The default configutations look for the model and scorer files in `${HOME}/deepspeech`.

Since the future DeepSpeech is currently looking uncertain you should also try out the Vosk speech-to-text engine. It's newer but seems to work well.

If the client is too slow at speech-to-text then you might want to consider off-loading some of the work to a machine with decent horse-power; see the `RemoteInput` class for doing that. The `PocketSphinxInput` class works with decent speed on a Raspberry Pi, but its accuracy isn't great.

It is recommended that you have only a single audio input. The reason for this is left as an exercise for the reader.

There are other simple input types mostly for physical interaction:
 * MediaKeyInput: This binds certain phrases to the media keys (Play, Stop, Next Track, Previous Track)
 * GPIO: Which binds certain phrases to the buttons on some HATs

### Outputs

These are ways to get Dexter's responses back to the user. These currently:
 * Speech-to-text via [Festival](http://www.cstr.ed.ac.uk/projects/festival/) and [ESpeak](http://espeak.sourceforge.net/).
 * Simple logging via the `LogOutput`
 * Transmission to an unsecured remote socket

### Services

The services are what actually handle the user requests. These might be things like playing music, telling you what the weather is, or setting some sort of timer. A simple `EchoService` is a basic example, and just says back to you what you said to it (quelle surprise!).

A quick overview of the current set of service modules is:
 * Bespoke: Canned responses to certain phrases
 * Chronos: Services to do with time (timers etc.)
 * Developer: Simple services to help with Dexter development work
 * Fortune: Pulls fortunes out of BSD Fortune
 * Language: Looking up words in a dictionary etc.
 * Music & Spotify: Play music from local disk, Spotify, etc.
 * PurpleAir: Look up stats from the [Purple Air](https://purpleair.com/) air sensors
 * Randomness: Various random generators
 * Volume: Sound control
 * WikiQuery: Look up things on Wikipedia

## Hardware

When using a Raspberry Pi 4 to drive Dexter I've found the following work for me:
 * [Samson Go Mic Portable USB Condenser Microphone](https://www.sweetwater.com/store/detail/GoMic--samson-go-mic-portable-usb-condenser-microphone)
 * One of these is useful to tell you what it's thinking (and the Mini HATs have buttons, which can be handy):
   - [Pimoroni Unicorn HAT Mini](https://shop.pimoroni.com/products/unicorn-hat-mini)
   - [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd)
   - [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini)
 * Any old speaker!

## Notes and Musings

This is an attempt to create a home assistant, akin to Google Home, Siri or Alexa, but without reliance on connecting to a proprietary cloud service to do the heavy lifting. It was originally designed to work on a Raspberry Pi running the standard Raspberry Pi OS, but also works on x86- 64 Ubuntu (as of 20.04.1). I've not tried it on Ubuntu on a Pi.

Right now, a bunch of basic services are there like setting timers, asking about things and playing music. That's pretty much most people tend to use their home assistant for anyhow it seems.

Writing components for Dexter should, in theory, be simple and intuitive. Most of the time you'll probably wind up writing services for it, though other types of notifier might be handy too. I generally find that you can get a beta version of something up and running in an hour or so. Of course, you then spend three more hours fiddling with it in various ways; that is probably the way of *most* coding projects though.

When it comes to getting Dexter working "right" the main thing I wind up doing is getting the sound quality good on the audio input. Some microphones are impressively bad and it's impressive that speech-to-text works at all with what they produce. So if you're having trouble, try setting the `wav_dir` argument of the audio input (e.g. to be `/tmp`) and listen to what it's getting. It will create files of the form `1604895798.wav`, where the number is seconds-since-epoch. You can then fiddle with the microphone settings (or use different microphones) until you get something which sounds okay.

It's far from perfect, and you will probably have to ask it to do something three times, but it's still kind of amazing that you can do all this on a $35 computer..! (Oh, with a $50 microphone, $15 HAT, $20 speaker, ...)

## Related work

Of course, Dexter isn't the only implementation of this idea. Other ones out there are:
 * [Jasper](https://jasperproject.github.io/)
 * [Mycroft](https://mycroft.ai/)
 * [Rhasspy](https://github.com/rhasspy/rhasspy)

How is Dexter different? Well, that's in the eye of the beholder really. The basic idea is the same, and they all have support for adding services (or equivalent) on your own. Of course, I can say without a hint of bias, that Dexter is the most awesome-est of the bunch. Like, I mean, dude: you can make it do swirly things with lights when it's listening to you or doing work. Who could ask for more?!

## Project status

Right now Dexter is at the point where it does pretty much what I wanted it to and so most of the work happening on it is related to bug fixes and tweaks, as opposed to adding new features. I'll also be keeping it ticking over with the updates to underlying libraries etc. so that it still works out of the box. Development work on it has been rather quiet of late, but don't consider it to be abandonware.

## Bugs

At some point it should be fixed to use `setup.py` to install itself.

If you are running with an unaccessible `DISPLAY` then you might see pygame do this:
```
Fatal Python error: (pygame parachute) Segmentation Fault
```
If that's the case, then simply unset the `DISPLAY` when running, e.g. with `env -u DISPLAY ./dexter.py -c config`.

The speech recognition could do with some work:
 * Not perfect at detecting the start and end of speech
 * It would be better if it continuously listened and picked up instructions as it went along

Some of the underlying libraries can hit fatal errors, causing the whole thing to `abort()` and die.
