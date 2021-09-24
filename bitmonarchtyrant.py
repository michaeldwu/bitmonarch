#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class BitMonarchTyrant(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.uploadHistory = []

        self.download_array = []
        self.upload_array = []

        self.pastround_chosen = []
        self.roundsOfUploads = []
        

    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []  # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Whenever a peer downloads a piece of the file, it sends per-piece have messages to the peers in its neighborhood. Each peer maintains
        # an estimate of the availibility of each piece by counting how many of its neighbors have the pieces.

        # NEED TO SORT BY RAREST FIRST RIGHT? Is this the place??
        peers.sort(key=lambda p: p.id)

        pieceCount = {}

        for peer in peers:
            avail_pieces = peer.available_pieces
            for piece in avail_pieces:
                if piece in pieceCount:
                    pieceCount[piece] += 1
                else:
                    pieceCount[piece] = 1

        rarestPieces = sorted(pieceCount, key=pieceCount.get)

        # Iterate through all peers
        #    For each peer, request the rarest pieces first
        for peer in peers:
            for piece_id in rarestPieces:
                if piece_id in np_set and piece_id in peer.available_pieces:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

        # Now that we have overall request list
        # Create new request list that orders requests by rarity
        request_c = requests.copy()
        sortedRequests = []
        for piece_id in rarestPieces:
            sortedwithinPiece = []
            for request in request_c:
                if piece_id == request.piece_id:
                    sortedwithinPiece.append(request)
                    request = None
            random.shuffle(sortedwithinPiece)
            sortedRequests.extend(sortedwithinPiece)

        return sortedRequests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers. Will contain available histories and
        history -- history for all previous rounds

        example history:
        AgentHistory(downloads=[[Download(from_id=Seed0, to_id=BitMonarchStd2, piece=0, blocks=1)], [Download(from_id=Seed0, to_id=BitMonarchStd2, piece=1, blocks=1)]], uploads=[[], []])

        returns: list of Upload objects.

        In each round, this will be called after requests().


            * Sort who's friendliest first to you (highest number of blocks in AgentHistory)
            * Check what pieces they need
            * If you have the piece they need, put them in your Upload slot
        """
        round = history.current_round()


        gamma = 0.1
        r = 3
        alpha = 0.2

        chosen = []
        bws = []

        num_peers = len(peers)
        if round == 0:
            download_rate = (self.conf.max_up_bw - self.conf.min_up_bw)/2/4
            # Try making upload_rate lower! -Jmack
            upload_rate = (self.conf.max_up_bw - self.conf.min_up_bw)/2/4

            self.download_array = [download_rate] * num_peers
            self.upload_array = [download_rate] * num_peers
            self.roundsOfUploads = [0] * num_peers
        else:
            
            # Update the values of unchoked

            # iterate through list of pastround_chosen
            # if pastround_chosen is in history.id
                # then we update their download value self.download_array

                # update self.roundsOfUploads[i]
                # if self.roundsOfUploads[i] >= r
                    # then we decrement then by b
            # else 
                # increase our upload setting for that index by (1+alpha)
            
            # pull out all the IDs for the people who let us download in the last round
            generousPeers = {}

            for download in history.downloads[-1]:
                if download.from_id in generousPeers:
                    generousPeers[download.from_id] = generousPeers[download.from_id] + download.blocks
                else:
                    generousPeers[download.from_id] = download.blocks


            for peer in self.pastround_chosen:
                if peer in generousPeers:
                    self.download_array[peer] = generousPeers[peer]
                    
                    self.roundsOfUploads[peer] += 1
                    if self.roundsOfUploads[peer] >= r:
                        self.upload_array[peer] = self.upload_array[peer] * (1- gamma)
                else:
                    self.upload_array[peer] = self.upload_array[peer] * (1 + alpha)
            

        ratio_dictionary = {i : self.download_array[i] / self.upload_array[i] for i in range(num_peers)}
        ratio_dictionary = dict(sorted(ratio_dictionary.items(), key=lambda item: item[1]))

        space_used = 0

        # iterate through sorted dictionary (give to best ratio)
        for key, value in ratio_dictionary.items():
            if (self.upload_array[key] + space_used <= self.up_bw):
                # give upload_array[key] to that key
                chosen.append(key)
                bws.append(self.upload_array[key])

                space_used += self.upload_array[key]
            else:
                # rando
                if len(requests) != 0:
                    
                    request = random.choice(requests)
                    chosen.append(int(request.requester_id[-1]))
                    bws.append(self.up_bw - space_used)
                break


        self.pastround_chosen = chosen

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
