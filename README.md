# Dexter

A voice controlled assistant, akin to Google Home and Alexa. Dexter's your right hand man (in theory).

This is very much a toy project and should be considered work in progress right now. It kinda works for me; it might for you too.

**Table of Contents**

- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running](#running)
- [Components](#components)
  - [Inputs](#inputs)
  - [Outputs](#outputs)
  - [Services](#services)


## Prerequisites

* [Python 2.7](https://www.python.org/).
* Around 4G of space, if you want to use PocketSphinx, DeepSpeech and so forth.
* What is listed in the `requirements` file.

You'll also need the trained data from [DeepSpeech](https://github.com/mozilla/DeepSpeech), which you should probably untar into `/usr/local/share/deepspeech`. (If you don't have root access then anywhere is fine really; this is just where I put it and so that's what the vanilla code expects.) This is only the barest of information; read their [project page](https://github.com/mozilla/DeepSpeech) for more information.


## Configuration

The configuration for Dexter is done via a [JSON](https://json.org/) file. Sorry, but it was the easiest way to do it. I guess I could have made it a Python file which you comment out bits of but that seemed more icky.

The file is expected to have two main dict entries: `key_phrases` and `components`. The `key_phrases` are a list of strings which Dexter will listen for in order to spot a command.

The `components` should be a dict with the following entires: `inputs`, `outputs` and `services`; each of these is a list of component defitions. Each component defition is a `[string,dict]` pair. The string is the fully-qualified name of the component class and the dict is a list of keyword arguments which will be used to instantiate the class.

See the `test_config` file as a simple example.

## Running

You can run the client like this:

```bash
./dexter.py -c test_config
```

## Components

There are three types of component in the system. You may have any number of each type, but it might not be wise in certain cases (e.g. multiple audio inputs probably won't work out well).

### Inputs

The inputs are ways to get requests into the system. A simple socket-based one is in `test_config` which you can telnet to and type into.

Inputs which convert spoken audio into text are also provided. These can be quite compute-intensive however, and so you might want to consider off-loading some of the work to a machine with decent horse-power, if your client is something like a Raspberry Pi. See the `RemoteInput` class for doing that. The `PocketSphinxInput` class works with decent speed on a Raspberry Pi, but its accuracy isn't great. The `DeepSpeechInput` class has great accuracy but takes about 35s for each second of input audio.

It is only recommended that you have a single audio input.


### Outputs

These are ways to get Dexter's responses back to the user. This might be simple logging via the `LogOutput` or an audio one, like `EspeakOutput`.


### Services

The services are what actually handle the user requests. These might be things like playing music, telling you what the weather is or setting some sort of timer. A simple `EchoService` is gives a basic example which just says back to you what you said to it.
