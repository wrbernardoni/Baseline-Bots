import random
from reconchess import *
from sortedcontainers import SortedList

class FullMonte(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.moveNum = 0
		self.nextMove = None
		self.expectedEnemy = None
		self.approxTime = 900
		self.interestingTile = None
		self.expectedScore = 0
		self.panic = False
		self.score = 0

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		if captured_my_piece:
			self.interestingTile = capture_square
			self.board.remove_piece_at(capture_square)

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		self.moveNum = self.moveNum + 1
		if self.panic:
			for square, piece in self.board.piece_map().items():
				if piece.color == self.color:
					sense_actions.remove(square)
			return random.choice(sense_actions)
		

		if self.interestingTile:
			return self.interestingTile

		if self.expectedEnemy is not None:
			if self.board.piece_at(self.expectedEnemy.to_square) is None:
				return self.expectedEnemy.to_square

		self.nextMove = self.choose_move(move_actions, seconds_left)
		if self.nextMove is not None:
			return self.nextMove.to_square

		for square, piece in self.board.piece_map().items():
			if piece.color == self.color:
				sense_actions.remove(square)

		return random.choice(sense_actions)

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		self.interestingTile = None
		for square, piece in sense_result:
			if self.board.piece_at(square) != piece:
				self.nextMove = None
				if self.board.piece_at(square) is None:
					if self.board.turn is self.color:
						self.board.push(chess.Move.null())
					for move in self.board.legal_moves:
						if move.to_square == square and self.board.piece_at(move.from_square) == piece:
							self.board.push(move)
							break


		#	if self.expectedEnemy is not None and piece is not None and self.board.piece_at(self.expectedEnemy.from_square) is not None:
		#		if self.expectedEnemy.to_square == square and self.board.piece_at(self.expectedEnemy.from_square).piece_type == piece.piece_type:
		#			self.board.push(self.expectedEnemy)

			if piece is None:
				self.board.remove_piece_at(square)
			else:
				self.board.set_piece_at(square, piece)

	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		self.approxTime = seconds_left
		self.response = None
		if self.nextMove is not None:
			mv = self.nextMove
			self.nextMove = None
			return mv

		if self.board.turn is not self.color:
			self.board.push(chess.Move.null())

		e_king_square = self.board.king(not self.color)
		if e_king_square:
			attackers = self.board.attackers(self.color, e_king_square)
			for attack in attackers:
				m = chess.Move(attack, e_king_square)
				if m in move_actions:
					return m

	#	m_king_square = self.board.king(self.color)
	#	if m_king_square:
	#		attackers = self.board.attackers(not self.color, m_king_square)
	#		if attackers:
	#			legalMoves = self.board.legal_moves
	#			for move in legalMoves:
	#				tempBoard = self.board.copy()
	#				tempBoard.push(move)
	#				attackers = tempBoard.attackers(not self.color, tempBoard.king(self.color))
	#				if (attackers is None or len(attackers) is 0) and move in move_actions:
	#					return move

		class State:
			def __init__(self, board, iM):
				self.brd = board
				self.score = 0
				self.initialMove = iM
				self.responses = SortedList(key=lambda x: x.score)

		def eval_board(board) -> float:
			score = 0
			for square, piece in board.piece_map().items():
				mult = 1
				attackers = board.attackers(not piece.color, square)
				defenders = board.attackers(piece.color, square)
				val = 0
				if piece.color != self.color:
					mult = -1
				if piece.piece_type == chess.PAWN:
					val = 5
				elif piece.piece_type == chess.KNIGHT:
					val = 10
				elif piece.piece_type == chess.BISHOP:
					val = 10
				elif piece.piece_type == chess.ROOK:
					val = 10
				elif piece.piece_type == chess.QUEEN:
					val = 20
				elif piece.piece_type == chess.KING:
					val = 100
				if len(attackers) != 0 and len(defenders) == 0 and piece.color == self.color:
					val = val / 10
				if len(defenders) != 0 and piece.piece_type != chess.KING:
					val = val * 2

				score = score + mult * val
			return score
		self.score = eval_board(self.board)

		trialsPer = 10
		depth = 10

		wasKing = False
		if self.board.king(not self.color):
			wasKing = True
			self.panic = False
		else:
			wasKing = False
			self.panic = True
		
		potentials = SortedList(key=lambda x: (x.score))
		for mv in self.board.legal_moves:
			startState = State(self.board.copy(), mv)
			startState.brd.push(mv)
			count = 0
			for resp in startState.brd.legal_moves:
				res = State(startState.brd.copy(), resp)
				res.brd.push(resp)
				scr = 0
				for i in range(trialsPer):
					tempBoard = res.brd.copy()
					tscr = 0
					for j in range(depth):
						e_king_square = tempBoard.king(not self.color)
						if e_king_square:
							attackers = tempBoard.attackers(self.color, e_king_square)
							if attackers:
								tscr = 1000
								break
						m_king_square = tempBoard.king(self.color)
						if m_king_square:
							attackers = tempBoard.attackers(not self.color, m_king_square)
							if attackers:
								tscr = -1000
								break
						potMoves = []
						for pM in tempBoard.legal_moves:
							potMoves.append(pM)
						if len(potMoves) != 0:
							tempBoard.push(random.choice(potMoves))
						else:
							tscr = -1000
							break
					if tscr == 0:
						tscr = eval_board(tempBoard)
					scr = scr + tscr
				scr = scr / trialsPer
				res.score = scr
				startState.responses.add(res)
				startState.score = startState.score + scr
				count = count + 1
			if count != 0:
				startState.score = startState.score / count
			else:
				startState.score = eval_board(startState.brd)

			potentials.add(startState)

		while len(potentials) > 0:
			top = potentials.pop(-1)
			if top.initialMove in move_actions:
				if len(top.responses) > 0:
					self.expectedEnemy = top.responses.pop(0).initialMove
				self.expectedScore = top.score
				return top.initialMove

		return random.choice(move_actions + [None])

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if taken_move is not None:
			self.board.push(taken_move)
		if requested_move is not taken_move:
			self.interestingTile = requested_move.to_square

		print ("fullMonte:\t End move ", self.moveNum, " -- approx ", '{:06.2f}'.format(self.approxTime), " seconds left || Score: ", '{:06.1f}'.format(self.score), "Expected Score: ", '{:06.1f}'.format(self.expectedScore))
		if self.panic:
			print("\tWe lost track of their king.")

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
