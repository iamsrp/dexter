# Dexter, A Voice Controlled Assistant

Dexter is a voice controlled assistant, akin to Google Home and Alexa. Dexter's your right hand person (in theory).

This is very much a toy project and should be considered work in progress. That being said, it kinda works for me; it might for you too.

**Table of Contents**

- [Quick start](#quickstart)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running](#running)
- [Components](#components)
  - [Inputs](#inputs)
  - [Outputs](#outputs)
  - [Services](#services)
  - [Notifiers](#notifiers)
- [Notes](#notes)
- [Bugs](#bugs)

## Quick start

If you quickly want to get up and running then:
 - Do a git clone of the repo
 - Install the prerequisites
 - Make sure that the appropriate model and scorer files are in `${HOME}/deepspeech`
 - Make sure you have a microphone and speaker
 - Try running dexter.py with the appropriate config file for your distro (either `pi_config` or `ubunutu_config`)
 You will then be hugely underwhelmed, but at least the basic functionality should be there at this point.

## Prerequisites

* [Python 3](https://www.python.org/).
* Around 1G of extra disk space, if you want to use DeepSpeech and so forth.
* Most of what is listed in the `requirements` file. What you actually need will depend on what components you add.

You'll also need the trained models and scorer from [DeepSpeech](https://github.com/mozilla/DeepSpeech). For more information on setting up DeepSpeech read their [project page](https://github.com/mozilla/DeepSpeech) and [documentation](https://deepspeech.readthedocs.io/).

When it comes to recording, make sure that you have a decent microphone with no noise; try listening to some `arecord` output to make sure it sounds clear. You can also provide a `wav_dir` argument for some of the audio input components, like `dexter.input.deepspeech.DeepSpeechInput`.

### Raspberry Pi Specifics

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
You can see the different hardware devices in `alsamixer`. You might also need to set the Audio Output in the System settings in `raspi-config` to your preference.

For input, DeepSpeech 0.9.0 onwards supports Tensorflow Light and it does a pretty decent job of recognition in near realtime. 

The Pi also has some really great, and cheap, HATs which can be used for user feedback on status (see below). The current code supports a couple of these but adding support for new ones is pretty easy, should you be feeling keen.

## Configuration

The configuration for Dexter is done via a [JSON](https://json.org/) file; sorry, but it was an easy way to do it. I guess I could have made it a Python file which you comment out bits of but that seemed more icky. Of course, JSON doesn't support comments so the default config files are not annotated.

The file is expected to have three main dict entries: `key_phrases`, `notifiers` and `components`. The `key_phrases` are a list of strings which Dexter will listen for, in order to spot a command. For example, "Dexter, what's the time?"

The `notifiers` are ways in which Dexter let's the user know what it's currently doing (e.g. actively listening, speaking back to you, etc.).

The `components` should be a dict with the following entires: `inputs`, `outputs` and `services`; each of these is a list of component defitions. Each component defition is a `[string,dict]` pair. The string is the fully-qualified name of the component class; the dict is a list of keyword arguments (kwargs; variable name & value pairs) which will be used to instantiate the class. The values in the kwargs may contain environment variables enclosed by dollar-sign-denoted curly braces, of the form `${VARIABLE_NAME}`.

See the `test_config` file as a simple example, and the platform specific ones which are more fleshed out.

## Running

You can run the client like this:

```bash
cd the_checkout_directory
./dexter.py -c test_config
```

### Notifiers

The Notifiers are how Dexter tells the user what it's doing. For example, if it has started listening or if it's querying an outside service, then it will effectively say so via simple means.

There are at least three right now:
 * A simple logging notifier, which writes to the console.
 * One for the [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd), which does whirly things.
 * One for the [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini), which does pulsey things.

## Components

There are three types of component in the system. You may have any number of each type, but it might not be wise in certain cases (e.g. multiple audio inputs probably won't work out well). The components plug into the system to provide its various functionality. Inputs are how commands get into the system, services handle the commands, and outputs give back the service results to the user.

The PyDoc for the different components should help you get up and running with them.

### Inputs

The inputs are ways to get requests into the system. A simple **unsecured** socket-based one is provided in `test_config`, which you can telnet to and type into.

Inputs which convert spoken audio into text are also provided. The `DeepSpeechInput` class has great accuracy but be sure to be using the versions which use TensorFlowLite (0.9.0 and up), since the prior versions are super slow. The default configutations look for the model and scorer files in `${HOME}/deepspeech`.

If the client is too slow at speech-to-text then you might want to consider off-loading some of the work to a machine with decent horse-power; see the `RemoteInput` class for doing that. The `PocketSphinxInput` class works with decent speed on a Raspberry Pi, but its accuracy isn't great. 

It is recommended that you have only a single audio input. The reason for this is left as an exercise for the reader.

### Outputs

These are ways to get Dexter's responses back to the user. This might be simple logging via the `LogOutput`, but there are also speech-to-text ones which use [Festival](http://www.cstr.ed.ac.uk/projects/festival/) and [ESpeak](http://espeak.sourceforge.net/).

### Services

The services are what actually handle the user requests. These might be things like playing music, telling you what the weather is, or setting some sort of timer. A simple `EchoService` is a basic example, and just says back to you what you said to it (quelle surprise!).

## Hardware

When using a Raspberry Pi 4 to drive Dexter I've found the following work for me:
 * [Samson Go Mic Portable USB Condenser Microphone](https://www.sweetwater.com/store/detail/GoMic--samson-go-mic-portable-usb-condenser-microphone)
 * One of these is useful:
   - [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd)
   - [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini)
 * Any old speaker!

## Notes and Musings

This is an attempt to create a home assistant, akin to Google Home, Siri or Alexa, but without reliance on connecting to a proprietary cloud service to do the heavy lifting. It was originally designed to work on a Raspberry Pi running the standard Raspberry Pi OS, but also works on x86_64 Ubuntu (as of 20.04.1). I've not tried it on Ubuntu on a Pi.

Right now, a bunch of basic services are there like setting timers, asking about things and playing music. That's pretty much most people tend to use their home assistant for anyhow it seems.

Writing components for Dexter should, in theory, be simple and intuitive. Most of the time you'll probably wind up writing services for it, though other types of notifier might be handy too. I generally find that you can get a beta version of something up and running in an hour or so. Of course, you then spend three more hours fiddling with it in various ways; that is probably the way of *most* coding projects though.

When it comes to getting Dexter working "right" the main thing I wind up doing is getting the sound quality good on the audio input. Some microphones are impressively bad and it's impressive that DeepSpeech works at all with what they produce. So if you're having trouble, try setting the `wav_dir` argument of the audio input (e.g. to be `/tmp`) and listen to what it's getting. It will create files of the form `1604895798.wav`, where the number is seconds-since-epoch. You can then fiddle with the microphone settings (or use different microphones) until you get something which sounds okay.

It's far from perfect, and you will probably have to ask it to do something three times, but it's still kind of amazing that you can do all this on a $35 computer..! (Oh, with a $50 microphone, $15 HAT, $20 speaker, ...)

## Bugs

At some point it should be fixed to use `setup.py` to install itself.

If you are running with an unaccessible `DISPLAY` then you might see pygame do this:
```
Fatal Python error: (pygame parachute) Segmentation Fault
```
If that's the case, then simply unset the `DISPLAY` when running, e.g. with `env -u DISPLAY ./dexter.py -c config`.

Detection of the start and end of speaking could also use some work. This has mainly been derived via a lot of trial and error; there is no doubt a better way to do this.