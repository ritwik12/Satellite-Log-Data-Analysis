from elasticsearch import Elasticsearch
import re
import timeit
import sys
import time
# progress bar
from tqdm import tqdm


# For analyse tool
def analyse(log_line, line, i):
    # For production.log related data only containing "Views"
    if log_line.find("production.log") != -1 and line.find("Views") != -1:
        i = i+1
        # Extract ID
        id = line[27:32]
        # Extract time
        log_time = line[11:19]
        # Extract total time
        totaltime = line[line.find("in")+3: line.find("in")+8]
        # Extract Views
        Views = line[line.find("Views")+7: line.find("Views")+12]
        # Extract ActiveRecord
        ActiveRecord = line[line.find("ActiveRecord")+14: line.find("ActiveRecord")+20]
        # Store data in JSON format to be indexed in ElasticSearch
        analyse_data = "ID:"+id+" "+"Time:"+log_time+" "+"Totaltime:"+totaltime+" "+"Views:"+Views+" "+"ActiveRecord:"+ActiveRecord
        if "json" in sys.argv:
            json = """{"index":{"_index":"production","_id":"""+'"'+str(i-1)+'"'+"""}} \n {"ID ":"""+'"'+id+'"'+""","Time":"""+'"'+log_time+'"'+""","Totaltime":"""+'"'+totaltime+'"'+""","Views":"""+'"'+Views+'"'+""","ActiveRecord":"""+'"'+ActiveRecord+'"'+"}"+"\n"
            # Write JSON formatted data to analyse.json
            file.write(json)
        else:
            print("---------------------------------------------------------------------------------------------------------")
            print(analyse_data)
            print("---------------------------------------------------------------------------------------------------------")
    #return analyse_data  # uncomment for unit tests


# For trace tool
def trace(line, trace_line):
    if line.find("[W") != -1 or line.find("[E") != -1:
        if line not in trace_line:
            trace_line.append(line)
    #return trace_line[0]  # uncomment for unit tests


# For consumer-id tool with specific log data corresponding to a particular consumer-id
def consumer(line, data, id):
    if line.find(id) != -1 and line.find("csid") != -1:
        csid = line[line.find("csid")+5: line.find("csid")+13]
        if csid != "" and csid.find("]") == -1 and len(csid) == 8:
            if csid not in data:
                # Adding csid as keys in dictionary i.e data
                data.update({csid: line})
            else:
                # Adding message lines as values in dictionary i.e data related to their respective csid
                data[csid] = [data[csid], line]
    #return data  # uncomment for unit tests


# For consumer-id tool with all log data
def all(line, data):
    if line.find("csid") != -1:
        csid = line[line.find("csid")+5:line.find("csid")+13]
        if csid != "" and csid.find("]") == -1 and len(csid) == 8:
            if csid not in data:
                # Adding csid as keys in dictionary i.e data
                data.update({csid: line})
            else:
                # Adding message lines as valeus in dictionary i.e data related to their respective csid
                data[csid] = [data[csid], line]
    #return data  # uncomment for unit tests


if __name__ == '__main__':
    # Run the code only if the argument passed is --all, --trace, --analyse or --consumer-id
    if [x for x in ["--all", "--consumer-id", "--trace", "--analyse"] if x in sys.argv]:
        start = timeit.default_timer()
        es = Elasticsearch()
        if len(sys.argv) == 4:
            time1 = sys.argv[2]  # Starting time of time range
            time2 = sys.argv[3]  # Ending time of time range
        if len(sys.argv) == 5:
            time1 = sys.argv[3]  # Starting time of time range
            time2 = sys.argv[4]  # Ending time of time range
        # scroll 10000 lines per scroll of all data for 10m, using maximum value for size i.e 10000
        if len(sys.argv) > 3:
            res = es.search(index="file3", scroll="10m", size="10000", body={"query": {"range": {"@timestamp": {"gte": time1, "lte": time2}}}})
        else:
            res = es.search(index="file3", scroll="10m", size="10000", body={"query": {"match_all": {}}})
        # scroll id to mark scroll
        sid = res['_scroll_id']
        scroll_size = res['hits']['total']
        ID = ""
        data = {}
        count = 0
        csid = ""
        trace_line = []
        if "--analyse" in sys.argv:
            file = open("analyse.json", "w")
        if "--consumer-id" in sys.argv:
            # Fetch consumer-id from second argument passed
            id = sys.argv[2]
        # Start scrolling
        while (scroll_size > 0):
            i = 0
            res = es.scroll(scroll_id=sid, scroll='10m')
            # Update the scroll ID
            sid = res['_scroll_id']
            # Get the number of results that we returned in the last scroll
            scroll_size = len(res['hits']['hits'])
            # tqdm is used for progress bar
            for doc in tqdm(res['hits']['hits']):
                # progress bar speed (iterations/sec)
                time.sleep(0.0000000000001)
                # Extarct log line from ElasticSearch
                log_line = "%s)%s" % (doc['_source']['source'], doc['_source']['message'])
                # Extract lines consisting only message from log lines
                line = "%s" % (doc['_source']['message'])
                # For analyse tool
                if "--analyse" in sys.argv:
                    analyse(log_line, line, i)
                # Trace errors and warnings
                elif "--trace" in sys.argv and log_line.find("production.log") != -1:
                    trace(line, trace_line)
                # For consumer-id tool
                elif [x for x in ["--all", "--consumer-id"] if x in sys.argv]:
                    # Find all the consumer ids present in ElasticSearch
                    consumer_id = re.search('[-a-zA-Z0-9]{36}', log_line)
                    # For production.log related data only
                    if consumer_id and log_line.find("production.log") != -1:
                        # Extract consumer id from a line
                        ID = log_line[consumer_id.start(): consumer_id.end()]
                    # For candlepin.log related data only
                    if log_line.find("candlepin.log") != -1 and ID != "":
                        # Find data for a particular consumer id
                        if "--consumer-id" in sys.argv:
                            consumer(line, data, id)
                        # Find all the data
                        elif "--all" in sys.argv:
                            all(line, data)
        if [x for x in ["--all", "--consumer-id"] if x in sys.argv]:
            for key, value in data.items():
                print("-------------------------------------------------------------------------------------------------------")
                print("CSID ->", key, "\n \n")
                print(str(value).replace(", '", "\n \n").strip("[").strip("'").strip("]"), "\n \n")
                print("-------------------------------------------------------------------------------------------------------")
        elif "--trace" in sys.argv:
            for i in range(len(trace_line)):
                print("-------------------------------------------------------------------------------------------------------")
                print(trace_line[i])
                print("------------------------------------------------------------------------------------------------------- \n \n")
        elif "--analyse" in sys.argv:
            print("-------------------------------------------------------------------------------------------------------")
            print("analyse.json created successfully")
            print("-------------------------------------------------------------------------------------------------------")
        stop = timeit.default_timer()
        print(stop - start)
    else:
        print("Wrong choice of arguments, Please choose from --all, --trace, --analyse or --consumer-id")
