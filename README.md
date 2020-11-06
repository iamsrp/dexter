# Dexter

A voice controlled assistant, akin to Google Home and Alexa. Dexter's your right hand person (in theory).

This is very much a toy project and should be considered work in progress right now. It kinda works for me; it might for you too.

**Table of Contents**

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


## Prerequisites

* [Python 3](https://www.python.org/).
* Around 1G of extra disk space, if you want to use DeepSpeech and so forth.
* What is listed in the `requirements` file.

You'll also need the trained data from [DeepSpeech](https://github.com/mozilla/DeepSpeech). For more information on setting up DeepSpeech read their [project page](https://github.com/mozilla/DeepSpeech) and [documentation](https://deepspeech.readthedocs.io/).

When it comes to recording, make sure that you have a decent microphone with no noise; try listening to some arecord output to make sure it sounds clear. You can also provide a `wav_dir` argument for some of the audio input components, like `dexter.input.deepspeech.DeepSpeechInput`.

### Raspberry Pi Specifics

If you're running Dexter on a Raspberry Pi then make sure that ALSA is working by testing `aplay` and `arecord`, tweaking volume with `alsamixer`. If it is not then you may well get strange errors from `pyaudio`. You might also want a `/home/pi/.asoundrc` file which looks something like this:
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
You can see the different hardware devices in `alsamixer`.

## Configuration

The configuration for Dexter is done via a [JSON](https://json.org/) file. Sorry, but it was the easiest way to do it. I guess I could have made it a Python file which you comment out bits of but that seemed more icky.

The file is expected to have two main dict entries: `key_phrases` and `components`. The `key_phrases` are a list of strings which Dexter will listen for in order to spot a command.

The `components` should be a dict with the following entires: `inputs`, `outputs` and `services`; each of these is a list of component defitions. Each component defition is a `[string,dict]` pair. The string is the fully-qualified name of the component class; the dict is a list of keyword arguments (kwargs) which will be used to instantiate the class or `None` if there aren't any. The values in the kwargs may contain environment variables enclosed by dollar-sign-denoted curly braces, of the form `${...}`.

See the `test_config` file as a simple example and `config` for a more complex one.

## Running

You can run the client like this:

```bash
./dexter.py -c test_config
```

## Components

There are three types of component in the system. You may have any number of each type, but it might not be wise in certain cases (e.g. multiple audio inputs probably won't work out well).

### Inputs

The inputs are ways to get requests into the system. A simple socket-based one is provided in `test_config`, which you can telnet to and type into.

Inputs which convert spoken audio into text are also provided. The `DeepSpeechInput` class has great accuracy but be sure to be using the versions which use TensorFlowLite (0.9.0 and up) since the prior versions are super slow. If the client is too slow then you might want to consider off-loading some of the work to a machine with decent horse-power; see the `RemoteInput` class for doing that. The `PocketSphinxInput` class works with decent speed on a Raspberry Pi, but its accuracy isn't great. 

It is only recommended that you have a single audio input.


### Outputs

These are ways to get Dexter's responses back to the user. This might be simple logging via the `LogOutput` but there are also speech-to-text ones which use ESpeak and [Festival](http://www.cstr.ed.ac.uk/projects/festival/).

### Services

The services are what actually handle the user requests. These might be things like playing music, telling you what the weather is or setting some sort of timer. A simple `EchoService` is gives a basic example which just says back to you what you said to it.

### Notifiers

The Notifiers are how Dexter tells the user what it's doing. For example, if it has started listening or if it's querying an outside service, then it will effectively say so via simple means.

There are at least three right now:
 * A simple logging notifier.
 * One for the [Pimoroni Unicorn HAT HD](https://shop.pimoroni.com/products/unicorn-hat-hd).
 * One for the [Pimoroni Scroll HAT Mini](https://shop.pimoroni.com/products/scroll-hat-mini).


## Notes

This is an attempt to create a home assistant, akin to Google Home, Siri or Alexa, but without reliance on connecting to a proprietary cloud service to do the heavy lifting. It's designed to work on a Raspberry Pi running Raspbian, but also works on Ubuntu (as of 20.04.1).

Right now, a bunch of basic services are there like setting timers, asking about things and playing music. That's pretty much most people tend to use their home assistant for anyhow it seems...

## Bugs

If you are running with an unaccessible DISPLAY then you might see pygame do this:
```
Fatal Python error: (pygame parachute) Segmentation Fault
```
If that's the case, then simply unset the DISPLAY when running, e.g. with `env -u DISPLAY ./dexter.py -c config`.
