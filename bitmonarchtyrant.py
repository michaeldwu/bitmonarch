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

        self.download_dict = {}
        self.upload_dict = {}
        self.roundsOfUploads = {}

        self.pastround_chosen = []

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

        # index is piece ID, value is how often it shows up

        # Iterate through all peers
        #    For each peer, request the rarest pieces first
        for peer in peers:
            for piece_id in rarestPieces:
                if (piece_id in np_set) and (piece_id in peer.available_pieces):
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)

        requests = sorted(requests, key=lambda x: (pieceCount[x.piece_id], random.random()))
        return requests

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
            # Trying to make upload_rate lower!
            upload_rate = (self.conf.max_up_bw - self.conf.min_up_bw)/2/4

            for peer in peers:
                self.download_dict[peer.id] = download_rate
                self.upload_dict[peer.id] = upload_rate
                self.roundsOfUploads[peer.id] = 0
        else:
            
            # Update the values of unchoked

            # iterate through list of pastround_chosen
            # if pastround_chosen is in history.id
                # then we update their download value self.download_dict

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
                    # Currently only updating downloads for if they were nice, can update downloads for everybody that gave me
                    self.download_dict[peer] = generousPeers[peer]
                    
                    self.roundsOfUploads[peer] += 1
                    if self.roundsOfUploads[peer] >= r:
                        self.upload_dict[peer] = self.upload_dict[peer] * (1- gamma)
                else:
                    self.upload_dict[peer] = self.upload_dict[peer] * (1 + alpha)
                    self.roundsOfUploads[peer] = 0

        ratio_dictionary = {peer.id : self.download_dict[peer.id] / self.upload_dict[peer.id] for peer in peers}
        ratio_dictionary = dict(sorted(ratio_dictionary.items(), key=lambda item: item[1], reverse=True))

        space_used = 0

        request_ids = [request.requester_id for request in requests]

        # iterate through sorted dictionary (give to best ratio)
        for key, value in ratio_dictionary.items():
            if key in request_ids:
                if (self.upload_dict[key] + space_used <= self.up_bw):
                    # give upload_array[key] to that key
                    # Don't upload to ourselves
                    if key != self.id:
                        chosen.append(key)
                        bws.append(self.upload_dict[key])

                        space_used += self.upload_dict[key]
                else:
                    # rando
                    if len(requests) != 0:
                        chosen.append(random.choice(request_ids))
                        bws.append(self.up_bw - space_used)
                    break

        self.pastround_chosen = chosen

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
