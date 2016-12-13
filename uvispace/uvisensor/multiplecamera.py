#!/usr/bin/env python
#Standard libraries
import glob
import logging
import numpy as np
import threading
#Local libraries
import imgprocessing
import videosensor
"""
Main routine for controlling an external FPGA with a camera device.

The main routine initializes 2 threads:

* The first thread interacts with the user through terminal. It reads
input commands, namely for finishing the program.
* The second thread contains the FGPA initialization process and an
infinite loop is continually requesting the UGV position to the FPGA.

------------------------
NOTE: The proper way to end the program is to press 'Q', as the terminal
prompt indicates during execution. Using the Keyboard Interrupt will 
probably corrupt the TCP/IP socket and the FPGA will have to be reset.
"""
class CameraThread(threading.Thread):
    """
    Create a thread and a VideoSensor object. Capture frames when run.
    """
    def __init__(self, begin_event, end_event, lock,
                 name=None, cfile=''):
        threading.Thread.__init__(self, name=name)
        #Initialize TCP/IP connection and FPGA operation.
        self.camera = videosensor.camera_startup(cfile)
        self.triangles = [None]
        self.begin_event = begin_event
        self.end_event = end_event
        self.lock = lock

    def run(self):
        #Locate shapes in whole image and configure trackers.
        videosensor.set_tracker(self.camera)
        self.begin_event.set()
        while not self.end_event.isSet():
            try:
                location = self.camera.get_register('ACTUAL_LOCATION')['1']
            except KeyError:
                continue
            location_array = np.array(location)
            image = imgprocessing.Image(contours=[location_array])
            #Obtain 3 vertices from the contours
            image.get_shapes(get_contours=False)
            #If no triangles are detected, avoid next instructions.
            if len(image.triangles):
                self.triangles[0] = image.triangles[0]
                logging.debug("detected triangle with vertices at {}"
                              "".format(image.triangles[0].vertices))
        logging.debug('shutting down {}'.format(self.name))
        videosensor.camera_shutdown(self.camera)


class DataFusionThread(threading.Thread):
    """
    Thread for assessing obtained shapes and merging the information.
    
    Merge the shapes obtained by each CameraThread and stored in a 
    global variable.
    """
    def __init__(self, lock, end_event, name='Fusion Thread'):
        threading.Thread.__init__(self, name=name)
        self.lock = lock
        self.end_event = end_event

    def run(self):
        while not self.end_event.isSet():
            pass


class UserThread(threading.Thread):
    """
    Thread for assessing obtained shapes and merging the information.
    
    Merge the shapes obtained by each CameraThread and stored in a 
    global variable.
    """
    def __init__(self, begin_events, end_event, 
                       name='User Thread', conf_file=''):
        """Inherit from threading.Thread and read event objects.
        
        begin_events is a list with N Event objects, where N is the 
        number of Camera threads started. Until the set up of every 
        camera is finished, the user can not interact with this thread.
        
        end_event is an event that indicates the end of the program.
        """
        threading.Thread.__init__(self, name=name)
        self.begin_events = begin_events
        self.end_event = end_event

    def run(self):
        for event in self.begin_events:
            event.wait()
        logging.info("All cameras were initialized")
        while not self.end_event.isSet():
            i = raw_input("Press 'Q' to stop the script...")
            if i == 'Q':
                self.end_event.set()


#Main routine
if __name__ == '__main__':
    logging.basicConfig(format=('%(asctime)s.%(msecs)03d '
                               '%(levelname)s (%(threadName)-9s):'
                               '%(message)s'), 
                        level=logging.DEBUG,
                        datefmt='%H:%M:%S',
                        filename='./log/main.log')
    log = logging.getLogger(__name__)
    logging.info("BEGINNING MAIN EXECUTION")
    #Get the relative path to all the config files stored in /config folder.
    conf_files = glob.glob("./resources/config/*.cfg")
    conf_files.sort()
    threads = []
    lock = threading.Lock()
    #A begin event for each camera will be created
    begin_events = []
    end_event = threading.Event()
    #New thread instantiation for each configuration file.
    for index, fname in enumerate(conf_files):
        begin_events.append(threading.Event())
        threads.append(CameraThread(begin_events[index], end_event, lock,
                                    'Camera{}'.format(index), fname))
    #Thread for getting user input
    threads.append(UserThread(begin_events, end_event))
    threads.append(DataFusionThread(lock, end_event))
    # start threads
    for thread in threads:
        thread.start()
    # wait for threads to end
    for thread in threads:
        thread.join()





