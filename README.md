# Ps5-Controller-Utils

First, lemme say I made this for playing schedule 1 while my keyboard was broken. Thank god for AI and the on-screen keyboard! I ended up making it compatible with most any game.

Next, lemme say I'll continue updating this as I see fit. If people want and need updates, I'll provide them, although I doubt people will use this, considering DS4 exists. I primarily wanted this for enhanced mouse controls compared to DS4 but ended up just replacing DS4 entirely in favor of allowing eight analog stick inputs for the left movement stick (I didn't forget about you lefties—there's support to swap left and right sticks).

Also, this is not a DS4 replacement; it only allows DualSense to use KBM inputs. It may not work in all games, especially games like Siege or Valorant with anti-cheats made specifically to block anti-recoil scripts, which it may be falsely detected as.

Lastly, this is only compatible with the DualSense controller for the PS5. Most likely, any other controller will not work, and DualSense Edge will likely work, but there's no guarantee from me, as I don't own one. Sorry, rich people(this a joke incase you're soft)!

# Directions:
pretty easy to setup

1. Install python 3.13 or similar(i.e. 3.11).

2. Run "pip install pystray pillow pynput pydirectinput dualsense-controller" in powershell To install any missing dependencies.

3. Run the CNK(Controller N' Keyoard).py script it will open in system tray.

4. If using the exe you should be good to skip steps 2 and 3 instead just run the exe after installing python and it will start in system tray.

5. If for any reason the exe doesnt work please report the error in Issues and provide any logs you can.

6. It should now be available from you're system tray set it up to you're liking and enjoy playing mnk games with a controller!!

# Pasted commentsVV
-- ... theres some compatibility options built in to help it work with you're preferred game 

-- if it doesnt work i suggest attempting to fix it yourself also please report any issues or incompatibilities to the github and ensure you post any fixes

-- it will likely not work on games with aggressive ac scanning I.E. Valorant/Siege you'll have to test it yourself


# KNOWN ERRORS
1. Deadzones dont work the default deadzone is alright but everyones deadzone preferences are different I've been struggling to make them work with this api im using but ill figure it out
