

import os, sys, glob, random, time





DIRECTORY = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(DIRECTORY)), "minilibs"))

import aimllib


BRAIN_FILE = os.path.join(DIRECTORY, "botbrain.brn")

kernelfile = None#BRAIN_FILE

aimlfiles = []
aimlfiles += glob.glob(os.path.join(DIRECTORY, "common_aiml", "*", "*.aiml"))
#aimlfiles += glob.glob(os.path.join(DIRECTORY, "handpicked_aiml", "*.aiml"))


# TO DUMP AIML FILES EXCEPT DJINN-SPECIFIC ONES 
kernel = aimllib.Kernel()
kernel.bootstrap(brainFile=kernelfile, learnFiles=aimlfiles)
kernel.saveBrain(BRAIN_FILE)
print ">>>>>>> dumped brain !"


aimlfiles += glob.glob(os.path.join(DIRECTORY, "djinn_specific_aiml", "*.aiml"))

sys.stdout.write("Connecting to www.djinns.from.heaven.com\n")

kernel = aimllib.Kernel()
kernel.verbose(True)
kernel.setBotPredicate("name", "Pay Rhuss")
kernel.setPredicate("name", "Oracle")

kernel.bootstrap(brainFile=kernelfile, learnFiles=aimlfiles)




print "\n"


print "*** Welcome to the shrine of the Oracles, young zealot ! ***"

print "\n"

while True: 
    q = raw_input("> ")
    time.sleep(float(random.randint(1,3))/3)
    print kernel.respond(q)
