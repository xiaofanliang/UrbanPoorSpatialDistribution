
# coding: utf-8

# In[ ]:


# scheduler.py
from mesa.time import RandomActivation
from collections import defaultdict


# Copy from WolfSheep Example.
# In Mesa, multiple agents including the patch, need to written as breed.
# Otherwise, a method is needed for each agent to identify their type.

class RandomActivationByBreed(RandomActivation):
    """
    """
    def __init__(self, model):
        super().__init__(model)
        self.agents_by_breed = defaultdict(dict)

    def add(self, agent):
        self._agents[agent.unique_id] = agent
        agent_class = type(agent)
        self.agents_by_breed[agent_class][agent.unique_id] = agent

    def remove(self, agent):
        del self._agents[agent.unique_id]

        agent_class = type(agent)
        del self.agents_by_breed[agent_class][agent.unique_id]

    def step(self, by_breed=True):
        if by_breed:
            for agent_class in self.agents_by_breed:
                self.step_breed(agent_class)
            self.steps += 1
            self.time += 1
        else:
            super().step()

    def step_breed(self, breed):
        agent_keys = list(self.agents_by_breed[breed].keys())
        random.shuffle(agent_keys)
        for agent_key in agent_keys:
            self.agents_by_breed[breed][agent_key].step()

    def get_breed_count(self, breed_class):
        return len(self.agents_by_breed[breed_class].values())


# In[ ]:


# model.py
from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import random 


def computeunhappyP(model):
    unhappyP = len([agent.happy for agent in model.schedule.agents 
                if type(agent) is PeopleAgent and agent.income == 1 and agent.happy == False])
    return unhappyP/model.schedule.get_breed_count(PeopleAgent)

def computeunhappyM(model):
    unhappyM = len([agent.happy for agent in model.schedule.agents 
                if type(agent) is PeopleAgent and agent.income == 2 and agent.happy == False])
    return unhappyM/model.schedule.get_breed_count(PeopleAgent)

def computeunhappyR(model):
    unhappyR = len([agent.happy for agent in model.schedule.agents 
                if type(agent) is PeopleAgent and agent.income == 3 and agent.happy == False])
    return unhappyR/model.schedule.get_breed_count(PeopleAgent)
            
class BurgessModel(Model):
    
    
    def __init__(self, N, width, height, layout):
        #super().__init__(seed)
        self.width = width
        self.height = height
        self.num_agents = N
        self.grid = MultiGrid(width, height, True)
        self.schedule = RandomActivationByBreed(self)
        self.running = True
            
        # Add the agent to a random grid cell
        def placeagent(oneAgent):
            x = random.randrange(self.grid.width)
            y = random.randrange(self.grid.height)
            self.grid.place_agent(oneAgent, (x, y))
    
        # Create People Agents
        id = 0
        for i in range(N//9*5):
            id += 1
            a = PeopleAgent(id, "poor", self)
            self.schedule.add(a)
            placeagent(a)
        for i in range(N//9*3):
            id += 1
            b = PeopleAgent(id, "middle", self)
            self.schedule.add(b)
            placeagent(b)
        for i in range(N//9):
            id += 1
            c = PeopleAgent(id, "rich", self)
            self.schedule.add(c)
            placeagent(c)
        
        # Creat Patches 
        id = N
        for agent, x, y in self.grid.coord_iter():
            id += 1
            patch = PatchAgent(id, (x, y), layout, self)
            self.grid.place_agent(patch, (x, y))
            self.schedule.add(patch)
            
        #create datacollector 
        self.datacollector = DataCollector(
            model_reporters={"UnhappyPoor": computeunhappyP, "UnhappyMid": computeunhappyM, "UnhappyRich": computeunhappyR})  
        
    def step(self):
        self.schedule.step()
        self.datacollector.collect(self)


# In[ ]:


#agents.py 

def matchpatch(step, model):
    return [agent for agent in model.schedule.agents if type(agent) is PatchAgent and agent.pos == step][0]
    
class PeopleAgent(Agent):
    
    def __init__(self, unique_id, category, model):
        super().__init__(unique_id, model)
        #added a parameter of category 
        self.category = category
        self.model = model
        self.happy = False
        self.overdue = 0
        
        if category == "poor": 
            self.income = 1
            self.dens_sens = 5
        elif category == "middle":
            self.income = 2
            self.dens_sens = 3
        elif category == "rich": 
            self.income = 3
            self.dens_sens = 1
        else: 
            raise Exception("category not found") 
    
    def move(self):
        # for each step of one agent, find possible neighbors within certain radius
        possible_steps = self.model.grid.get_neighborhood(
            self.pos,
            True,
            radius = 5,
            include_center=False)
        
        #pick one of the possible steps that has income >= Lprice, dens_sens >= density, (later job_probs)
        #the patch that has the same location as step
        
        qualified_positions = [step for step in possible_steps 
                               if self.income >= matchpatch(step, self.model).Hprice 
                               and random.random() <= matchpatch(step, self.model).jobs_prob 
                               and self.dens_sens >= matchpatch(step, self.model).density
                              ]
            
        #If no qualfied positions available
        if not qualified_positions: 
            qualified_positions = [self.pos]
            self.overdue += 1
        
        if self.overdue > self.income:
            self.model.schedule.remove(self)
        else: 
            new_position = random.choice(qualified_positions)
            self.model.grid.move_agent(self, new_position)
    
    #update agent happiness
    
    def updatehappiness(self):
        patch = matchpatch(self.pos, self.model)
        self.happy = self.income >= patch.Hprice and random.random() <= patch.jobs_prob and self.dens_sens >= patch.density
        
    def step(self):
        # check if income still higher than Lprice and job maintains
        self.updatehappiness()
        if not self.happy: 
            self.move()
        self.updatehappiness()
        pass


class PatchAgent(Agent):
    
    def __init__(self, unique_id, pos, layout, model):
        super().__init__(unique_id, model)
        self.model = model 
        self.pos = pos
        self.layout = layout 

        #assume the range of CBD, urban, suburban is 2:4:4 (arbitrary)
        width = self.model.width
        lt_exp = width/2 - 1 #4
        rt_exp = width/2 #5
        rt_mid = rt_exp + width/5 #7
        lt_mid = lt_exp - width/5 #2
        x = self.pos[0]
        y = self.pos[1]
        
        #-------- Assign job probability and land price distribution ----------. 
        #high
        if rt_exp >= x >= lt_exp and rt_exp >= y >= lt_exp: 
            
            #high job distribution
            self.jobs_prob = random.normalvariate(0.7, 0.1)
            
            #80% chance of having the most expensive price (arbitrary)
            if random.random() >= 0.2:
                self.Lprice = 3
            else:
                self.Lprice = 2
        #low
        elif ((lt_mid > x >= 0 or width -1 >= x > rt_mid) and (width - 1 >= y >= 0)) or ((lt_mid > y >= 0 or width - 1 >= y > rt_mid) and (width - 1 >= x >= 0)):
            self.jobs_prob = self.jobs_prob = random.normalvariate(0.3, 0.1)
            self.Lprice = random.randint(1,2)
            
        #middle
        else:
            self.Lprice = random.randint(2,3)
            self.jobs_prob = random.normalvariate(0.5, 0.1)
            
        # ---- Caculate the amount of agents on each patch ---------. 
        self.density = len(self.model.grid.grid[self.pos[0]][self.pos[1]])-1 
        
        # ---- Caculate the Housing price given land price and density -----. (This is quite arbitrary right now)
        if self.density == 0:
            self.Hprice = self.Lprice
        else:
            self.Hprice = self.Lprice/self.density
    
    def step(self):
        #count number of people on the same patch and update density
        self.density = len(self.model.grid.grid[self.pos[0]][self.pos[1]])-1
        


# In[ ]:


test = BurgessModel(90,10,10,"land_price")
test.step()


# In[ ]:


#server.py

from mesa.visualization.modules import CanvasGrid
from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import ChartModule
from mesa.visualization.UserParam import UserSettableParameter

def agent_portrayal(agent):
    if type(agent) is PatchAgent:
        portrayal = {"Shape": "rect",
                     "Filled": "true",
                     "Layer": 0,
                     "w": 1,
                     "h": 1,
                     "Color": "white",
                    }
        if agent.layout == "land_price":
            if agent.Lprice == 3: 
                portrayal["Color"] = "LightGrey"
            elif agent.Lprice == 2:
                portrayal["Color"] = "Grey"
            else: 
                portrayal["Color"] = "black"
                
        elif agent.layout == "job_prob":
            portrayal["Color"] = "hsl(0, 0%, "+str(agent.jobs_prob * 100)+"%)"
        
        #a better density calculation can be designed. 
        elif agent.layout == "density":
            portrayal["Color"] = "hsl(0, 0%, "+str(agent.density * 10)+"%)"
        
        else: raise Exception("Agent Layer not found") 
                
        
    elif type(agent) is PeopleAgent: 
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "r": 0.5}
        if agent.category == 'poor':
            portrayal["Color"] = "red"
        elif agent.category == 'middle':
            portrayal["Color"] = "yellow"
            portrayal["Layer"] = 2
            portrayal["r"] = 0.4
        else: 
            portrayal["Color"] = "green"
            portrayal["Layer"] = 3
            portrayal["r"] = 0.3
            
    else: raise Exception("Agent Portrayal not found") 
            
    return portrayal

#the width and height can only be multiple of 10. 
width = 10
height = 10 

grid = CanvasGrid(agent_portrayal, width, height, 500, 500)

chart = ChartModule([{"Label": "UnhappyPoor",
                      "Color": "Red"},
                     {"Label": "UnhappyMid",
                      "Color": "Yellow"},
                     {"Label": "UnhappyRich",
                      "Color": "Green"}
                    ],
                    data_collector_name='datacollector')

n_slider = UserSettableParameter("slider", "Number of Agents", 90, 90, 900, 9)
layout_choice = UserSettableParameter("choice", "Layout Choices", value = "land_price",
                                      choices = ["land_price", "job_prob", "density"])

userparameters = {"N": n_slider, 
                  "width": width, 
                  "height": height,
                  "layout": layout_choice,
                 }

server = ModularServer(BurgessModel,
                       [grid, chart],
                       "Burgess Model",
                       userparameters)



# In[ ]:


server.port = 8521 # The default
server.launch()


# In[ ]:


#Better Flexibility 
#1/ probability layout (e.g. 2D gaussian distribution?)

#Better visualization 
#1/ Switch layout without step or reset. 

#Better performance 
#1/ very slow. 
#2/ smarter system for density sensitivity 
