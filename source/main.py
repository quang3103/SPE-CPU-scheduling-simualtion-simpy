import simpy
import numpy.random as random
import math

LAMBDA = 10
MU = 20
QUANTUM_TIME = 10
GENERATE_MODE = 2


def write_to_file(file, time, who, msg):
    file.write("{}:{}{}:{}{}\n".format(time, " " * (10 - len(str(time))), who, " " * (20 - len(who)), msg))


def write_queue_to_file(file, time, which, queue):
    file.write("{}:{}{}: ".format(time, " " * (10 - len(str(time))), which, " " * (20 - len(which))))
    for job in queue:
        file.write(str(job.id) + " ")
    file.write("\n")


def write_statistic_to_file(file, job):
    file.write("process:{},arrival:{},burst_time:{},turn_around:{},response:{},waiting:{}\n".format(job.id, job.arrival_time, job.saved_burst_time, job.turn_around_time, job.response_time, job.waiting_time))


class Job:
    def __init__(self, id, arrival_time, burst_time, priority):
        self.id = id
        self.arrival_time = arrival_time
        self.last_time_in_CPU = arrival_time
        self.saved_burst_time = burst_time
        self.burst_time = burst_time
        self.priority = priority
        self.turn_around_time = 0
        self.waiting_time = 0
        self.response_time = -1


class JobGenerator:
    def __init__(self, env):
        self.env = env
        self.inter_arrivaltime = 1 / LAMBDA
        self.service_time = 1 / MU

    def generate_job(self, mode, cpu_scheduling):
        i = 0
        while True:
            if mode == 0:
                yield self.env.timeout(9)
                if i % 2 == 0:
                    cpu_scheduling.handle_arrival_job(Job(i, self.env.now, 10, 0))
                else:
                    cpu_scheduling.handle_arrival_job(Job(i, self.env.now, 10, 1))
                i += 1
            elif mode == 1:
                yield self.env.timeout(15)
                cpu_scheduling.handle_arrival_job(Job(i, self.env.now, 10, 0))
                i += 1
            elif mode == 2:
                job_interarrival = math.trunc(random.exponential(self.inter_arrivaltime) * 100)
                yield env.timeout(job_interarrival)
                job_duration = math.trunc(random.exponential(self.service_time) * 100) + 1
                priority = random.randint(0, 2)
                cpu_scheduling.handle_arrival_job(Job(i, self.env.now, job_duration, priority))
                i += 1


class CPU:
    def __init__(self, env):
        self.env = env
        self.job_arrival_interrupt = env.event()
        self.idle_time = 0

    def serve(self, time, job):
        write_to_file(log_file, self.env.now, "CPU", "CPU is GIVEN TO process {}".format(job.id))
        try:
            yield self.env.timeout(time)
        except simpy.Interrupt as i:
            print("Interrupt: " + i.cause)
        write_to_file(log_file, self.env.now, "CPU", "Process {} LEAVE the CPU".format(job.id))
        job.last_time_in_CPU = self.env.now

    def idle(self):
        # print("{} cpu is idle".format(self.env.now))
        write_to_file(log_file, self.env.now, "CPU", "CPU is IDLE")
        t1 = self.env.now
        yield self.job_arrival_interrupt
        self.idle_time += (self.env.now - t1)


class CpuScheduling:
    def __init__(self, env, quantum_time=5):
        self.env = env
        self.quantum_time = quantum_time
        self.RR_queue = []
        self.FCFS_queue = []
        self.CPU = CPU(self.env)

    def handle_arrival_job(self, job):
        if job.priority == 0:
            # print("{}: Receive 1 job with priority 0".format(self.env.now))
            '''put this job to RR queue'''
            write_to_file(log_file, self.env.now, "RR queue", "Process {} burst time {} to RR queue".format(job.id, job.burst_time))
            self.RR_queue.append(job)
            write_queue_to_file(queue_file, self.env.now, "RR queue", self.RR_queue)
        elif job.priority == 1:
            # print("{}: Receive 1 job with priority 1".format(self.env.now))
            '''put this job to FCFS queue'''
            write_to_file(log_file, self.env.now, "FCFS queue", "Process {} burst time {} to FCFS queue".format(job.id, job.burst_time))
            self.FCFS_queue.append(job)
            write_queue_to_file(queue_file, self.env.now, "FCFS queue", self.FCFS_queue)

        self.CPU.job_arrival_interrupt.succeed()
        self.CPU.job_arrival_interrupt = self.env.event()

    def schedule(self):
        while True:
            '''check if there are any processes are waiting to be executed'''
            if (len(self.RR_queue) != 0) or (len(self.FCFS_queue) != 0):

                '''Execute all processes in RR queue'''
                while len(self.RR_queue) != 0:
                    write_queue_to_file(queue_file, self.env.now, "RR queue", self.RR_queue)
                    '''Get the process of out the queue'''
                    my_job = self.RR_queue.pop(0)

                    '''Calculate statistics of the process'''
                    if my_job.response_time == -1:
                        my_job.response_time = self.env.now - my_job.arrival_time
                    my_job.waiting_time += (self.env.now - my_job.last_time_in_CPU)

                    '''calculate duration for this process in RR algorithm'''
                    duration = min(self.quantum_time, my_job.burst_time)
                    yield self.env.process(self.CPU.serve(duration, my_job))
                    my_job.burst_time -= duration

                    '''Check if the process finishes or not'''
                    if my_job.burst_time > 0:
                        my_job.priority += 1
                        self.FCFS_queue.append(my_job)
                        write_to_file(log_file, self.env.now, "FCFS queue", "Process {} burst time {} to FCFS queue".format(my_job.id, my_job.burst_time))
                        write_queue_to_file(queue_file, self.env.now, "FCFS queue", self.FCFS_queue)
                    else:
                        '''Yes, this process finish. We calculate some other statistics'''
                        my_job.turn_around_time = self.env.now - my_job.arrival_time
                        assert my_job.turn_around_time == my_job.saved_burst_time + my_job.waiting_time
                        write_statistic_to_file(stat_file, my_job)

                ''' Execuet all process in FCFS queue'''
                while len(self.FCFS_queue) != 0:
                    write_queue_to_file(queue_file, self.env.now, "FCFS queue", self.FCFS_queue)
                    '''Get the process of out the queue'''
                    my_job = self.FCFS_queue.pop(0)

                    '''Calculate some statistics of the process'''
                    if my_job.response_time == -1:
                        my_job.response_time = self.env.now - my_job.arrival_time
                    my_job.waiting_time += (self.env.now - my_job.last_time_in_CPU)

                    '''In process with lower priority could be preempted by higher priority process'''
                    t1 = self.env.now
                    serve_proc = self.env.process(self.CPU.serve(my_job.burst_time, my_job))

                    '''wait for the process to finish or there is interrupt because
                       there is higher priority process comes'''
                    results = yield serve_proc | self.CPU.job_arrival_interrupt

                    '''Check if our process completely finishes or be interrupted by higher priority process'''
                    if serve_proc not in results:
                        serve_proc.interrupt("Higher priority process comes!")
                        interval = self.env.now - t1
                        my_job.burst_time -= interval

                        '''put the interrupted process back into FCFS queue and break'''
                        self.FCFS_queue.append(my_job)
                        write_to_file(log_file, self.env.now, "FCFS queue", "Process {} burst time {} to FCFS queue".format(my_job.id, my_job.burst_time))
                        write_queue_to_file(queue_file, self.env.now, "FCFS queue", self.FCFS_queue)
                        break
                    else:
                        '''there is no process with higher priority comes and the process completely finish.
                            We calculate some statistics for this process'''
                        my_job.turn_around_time = self.env.now - my_job.arrival_time
                        assert my_job.turn_around_time == my_job.saved_burst_time + my_job.waiting_time
                        write_statistic_to_file(stat_file, my_job)
            else:
                '''No process wait, therefore the CPU will go to IDLE state'''
                yield self.env.process(self.CPU.idle())


class Simulation:
    def __init__(self, env):
        self.my_job_generator = JobGenerator(env)
        self.my_cpu_scheduling = CpuScheduling(env, QUANTUM_TIME)

    def simulate(self):
        env.process(self.my_job_generator.generate_job(GENERATE_MODE, self.my_cpu_scheduling))
        env.process(self.my_cpu_scheduling.schedule())


path_file = "./output/mode" + str(GENERATE_MODE)
print(path_file)
log_file = open(path_file + "/log.txt", "w")
stat_file = open(path_file + "/stat.txt", "w")
queue_file = open(path_file + "/queue.txt", "w")
env = simpy.Environment()
sim = Simulation(env)
sim.simulate()
env.run(until=1000)
