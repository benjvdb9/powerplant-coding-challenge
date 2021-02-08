import json
import flask

class LoadBalancer:
    def __init__(self, importfile, file):
        if not importfile:
            self.__payload = file
        else:
            self.__payload = self.__readJson(file)
        self.__current_load = 0
        self.__load  = self.__payload["load"]
        self.__fuels = self.__payload["fuels"]
        self.__windturbines = []
        self.__contenders = []
        self.__pload = []

    def __readJson(self, file):
        with open(file, "r") as f:
            payload = f.read()
            payload = json.loads(payload)
            f.close()
        return payload

    def __getPPM(self, plant):
        if plant["type"] == 'gasfired':
            price_per_MWh = self.__fuels["gas(euro/MWh)"]
        elif plant["type"] == 'turbojet':
            price_per_MWh = self.__fuels["kerosine(euro/MWh)"]
        elif plant["type"] == 'windturbine':
            price_per_MWh = 0

        return price_per_MWh / plant["efficiency"]

    def __getLoads(self):
        load_gap = self.__load - self.__current_load
        next_contender_load = []

        for index_num in range(len(self.__contenders)):
            if self.__contenders[index_num]["pmin"] > load_gap:
                next_contender_load += [-1]
            elif self.__contenders[index_num]["pmax"] > load_gap:
                next_contender_load += [load_gap]
            else:
                next_contender_load += [self.__contenders[index_num]["pmax"]]

        return next_contender_load

    def __balanceWindTurbines(self):
        while len(self.__windturbines) > 0:
            highest_pmax = self.__windturbines.pop(self.__windturbines.index(
                            max(self.__windturbines, key=lambda x : x[1])))
            
            r = self.__balanceLoad(*highest_pmax)
            if r == -2:
                print("skip to results")

    def __balanceOtherTurbines(self):
        price_per_MWh = []
        for plant in self.__contenders:
            temp_price = self.__getPPM(plant)
            price_per_MWh += [temp_price]

        while self.__current_load != self.__load:
            prices_ranked = []
            load_gap = self.__load - self.__current_load
            prices = price_per_MWh.copy()

            while len(prices) != 0:
                local_min = [i for i, val in enumerate(prices) if val == min(prices)]
                price = prices[local_min[0]]
                for i in sorted(local_min, reverse=True):
                    del(prices[i])
                prices_ranked += [[(i, self.__contenders[i]["pmax"], self.__contenders[i]["pmin"]) for\
                                    i, val in enumerate(price_per_MWh) if val == price]]

            
            i = 0
            balance  = []
            balanced = False
            while i < len(prices_ranked) and not balanced:
                pmax_list = [b for a, b, c in prices_ranked[i]]
                pmin_list = [c for a, b, c in prices_ranked[i]]
                pmax_sum = sum(pmax_list)
                pmin_sum = sum(pmin_list)
                if pmax_sum >= load_gap:
                    if pmin_sum <= load_gap:
                        temp_balance = [i / pmin_sum for i in pmin_list]
                        balance += [[round(load_gap*ratio, 1) for ratio in temp_balance]]
                    else:
                        min_copy = prices_ranked.copy()
                        while pmin_sum > load_gap:
                            smallest_pmin_i = min(min_copy[i], key=lambda x : x[2])
                            del(min_copy[smallest_pmin_i[0]])
                            del(min_copy[smallest_pmin_i[0]])
                            pmax_sum = sum([b for a, b, c in min_copy[i]])
                            pmin_sum = sum([c for a, b, c in min_copy[i]])
                        if pmax_sum >= load_gap:
                            pmin_list = []
                            for elem in prices_ranked[i]:
                                found = False
                                for elem2 in min_copy[i]:
                                    if elem[0]  == elem2[0]:
                                        found = True
                                        pmin_list += [elem[2]]
                                if not found:
                                    pmin_list += [0]
                            temp_balance += [i / pmin_sum for i in pmin_list]
                            balance = [[round(load_gap*ratio, 1) for ratio in temp_balance]]
                        else:
                            i+=1

                i = 0
                j = 0
                sorted_load_balance = [0 for a in range(len(self.__contenders))]
                while i < len(prices_ranked):
                    while j < len(prices_ranked[i]):
                        try:
                            sorted_load_balance[prices_ranked[i][j][0]] = balance[i][j]
                        except:
                            sorted_load_balance[prices_ranked[i][j][0]] = 0
                        j+=1
                    i+=1

                if sum([x for sublist in balance for x in sublist]) != load_gap:
                    difference = load_gap - sum(balance)
                    balance[0] += round(difference, 1)

                for index in sorted(range(len(sorted_load_balance)), reverse=True):
                    self.__balanceLoad(self.__contenders[index], sorted_load_balance[index])
                    del(self.__contenders[index])

                if self.__current_load == self.__load:    
                    balanced = True

                


    def __balanceLoad(self, plant, load):
        load_to_check = self.__current_load + load
        if load_to_check == self.__load:
            self.__current_load = round(self.__current_load + load, 1)
            self.__updatePLoad(plant, load)
            return -2
        elif load_to_check < self.__load:
            self.__current_load = round(self.__current_load + load, 1)
            self.__updatePLoad(plant, load)
            return load
        else:
            raise SystemError("Balancer Error")

    def __updatePLoad(self, plant, load):
        for elem in self.__pload:
            if elem["name"] == plant["name"]:
                elem["p"] = load

    def __properPLoad(self, plant):
        if plant["type"] == "windturbine":
            wind_power = round(plant["pmax"] * self.__fuels["wind(%)"] / 100, 1)
            self.__windturbines += [(plant, wind_power)]
        else:
            self.__contenders += [plant]

        self.__pload += [{"name" : plant["name"], "p" : 0}]

    def globGetter(self):
        print(self.__current_load)
        print(self.__load)
        print(self.__fuels)
        print(self.__windturbines)
        print(self.__contenders)
        print(self.__pload)


    #Main function
    def CalcCost(self):
        for plant in self.__payload["powerplants"]:
            self.__properPLoad(plant)

        self.__balanceWindTurbines()
        self.__balanceOtherTurbines()
        return json.dumps(self.__pload, indent=4)

app = flask.Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    #data = flask.request.form
    #print(data)
    return "HELLO"

@app.route('/productionplan', methods=['POST'])
def productionplan():
    data = flask.request.json
    #regex to verify data here
    LB1 = LoadBalancer(False, data)
    result = LB1.CalcCost()

    return result

app.run('localhost', port=8888)