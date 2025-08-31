# Ps5-Controller-Utils

first lemme say i made this for playing schedule 1 while my keyboard was broken thank god for ai and the on-screen-keyboard ended up making it compatible with most any game.

next lemme say I'll continue updating this as I see fit if people want and need updates I'll provide them although I doubt people will use this considering ds4 exists I primarily wanted this for enhanced mouse controls compared to ds4 but ended up just replacing ds4 entirely in favor of allowing 8 analog stick inputs for the left movement stick(I didnt forget about you lefty's theres support to swap left and right stick).

also this is not a ds4 replacement it only allows dualsense to use kbm inputs also it may not work in all games especially games like siege or valorant with anticheats made specifically to block anti-recoil scripts which it may be falsely detected as.

lastly this is only compatible with the dualsense controller for the ps5 most likely any other controller will not work and dualsense edge will likely work but no guarentee from me as I dont own one sorry rich people.

# Directions:
pretty easy to setup

1. install python 3.13 or similar(i.e. 3.11).

2. Run "pip install pystray pillow pynput pydirectinput dualsense-controller" in powershell To install any missing dependencies.

3. Run the CNK(Controller N' Keyoard).py script it will open in system tray.

4. if using the exe you should be good to skip steps 2 and 3 instead just run the exe after installing python and it will start in system tray.

5. if for any reason the exe doesnt work please report the error in Issues and provide any logs you can.

6. It should now be available from you're system tray set it up to you're liking and enjoy playing mnk games with a controller!!

# Pasted commentsVV
-- as such theres some compatibility options built in to help it work with you're preferred game 

-- if it doesnt work i suggest attempting to fix it yourself also please report any issues or incompatibilities to the github and ensure you post any fixes

-- it will likely not work on games with aggressive ac scanning I.E. Valorant/Siege you'll have to test it yourself


# KNOWN ERRORS
1. Deadzones dont work the default deadzone is alright but everyones deadzone preferences are different I've been struggling to make them work with this api im using but ill figure it out
