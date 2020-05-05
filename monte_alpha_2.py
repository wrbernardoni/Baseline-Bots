import random
from reconchess import *
from sortedcontainers import SortedList
from multiprocessing import Pool, TimeoutError

# Hopefully optimized version of MonteAlpha
def true_eval(color, board) -> float:
	num = 0
	for square, piece in board.piece_map().items():
		mult = 1
		val = 0
		if piece.color != color:
			mult = -1
		if piece.piece_type == chess.PAWN:
			val = 1
		elif piece.piece_type == chess.KNIGHT:
			val = 10
		elif piece.piece_type == chess.BISHOP:
			val = 10
		elif piece.piece_type == chess.ROOK:
			val = 10
		elif piece.piece_type == chess.QUEEN:
			val = 20
		elif piece.piece_type == chess.KING:
			val = 1000
			attackers = board.attackers(not piece.color, square)
			if len(attackers) != 0:
				num = num - mult * 500
				if piece.color == color:
					num = num - 500
		num = num + mult * val
	return num/2

def eval_board(color, panic, board) -> float:
	trials = 5
	trialDepth = 10
	score = 0
	inp = []
	for i in range(trials):
		tBoard = board.copy()
		won = False
		for j in range(trialDepth):
			if not board.king(color):
				score = score - 1000
				won = True
				break

			if not panic:
				if not board.king(not color):
					score = score + 1000
					won = True
					break

			potMoves = []
			for mv in board.pseudo_legal_moves:
				potMoves.append(mv)
			if len(potMoves) == 0:
				break
			m = random.choice(potMoves)
			board.push(m)
		if not won:
			num = true_eval(color, board)
			score = score + num
			
	return score / trials

def alphabeta(inp) -> float:
	(color, panic, board, depth, alpha, beta, maximizing) = inp
	terminal = False
	mod = 0
	if not panic:
		e_king_square = board.king(not color)
		if not e_king_square:
			terminal = True
			mod = 1000
		elif maximizing:
			attackers = board.attackers(color, e_king_square)
			if attackers:
				mod = 1000
				terminal = True
	m_king_square = board.king(color)
	if not m_king_square:
		terminal = True
		mod = -1000
	elif not maximizing:
		attackers = board.attackers(not color, m_king_square)
		if attackers:
			mod = -1000
			terminal = True
	if depth == 0 or terminal:
		return (eval_board(color, panic, board) + mod, None, None)

	if maximizing:
		if board.turn != color:
			board.push(chess.Move.null())
		val = float("-inf")
		bM = []
		for mv in board.pseudo_legal_moves:
			tB = board.copy()
			tB.push(mv)
			(v, m, r) = alphabeta((color, panic, tB, depth - 1, alpha, beta, False))

			if v > val:
				bM = [(mv, m)]
				val = v
			elif v == val:
				bM.append((mv,m))

			alpha = max(alpha, val)
			if alpha >= beta:
				break
		if len(bM) == 0:
			return (val, None, None)
		else:
			(mov, resp) = random.choice(bM)
			return (val, mov, resp)
	else:
		if board.turn == color:
			board.push(chess.Move.null())
		val = float("inf")
		bM = []
		res = []
		for mv in board.pseudo_legal_moves:
			tB = board.copy()
			tB.push(mv)
			(v, m, r) = alphabeta((color, panic, tB, depth - 1, alpha, beta, True))

			if v < val:
				bM = [(mv, m)]
				val = v
			elif v == val:
				bM.append((mv,m))

			beta = min(beta, val)
			if alpha >= beta:
				break
		if len(bM) == 0:
			return (val, None, None)
		else:
			(mov, resp) = random.choice(bM)
			return (val, mov, resp)

class MonteAlpha2(Player):
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
		self.observedMoves = 0

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		print("")
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
			print("Scanning interesting tile")
			return self.interestingTile

		if self.expectedEnemy is not None:
			if self.board.piece_at(self.expectedEnemy.to_square) is None:
				print("Scanning expected move")
				return self.expectedEnemy.to_square

		self.nextMove = self.choose_move(move_actions, seconds_left)
		if self.nextMove is not None:
			print("Scanning next move")
			return self.nextMove.to_square

		for square, piece in self.board.piece_map().items():
			if piece.color == self.color:
				sense_actions.remove(square)

		print("Scanning random")
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

		if self.board.king(not self.color):
			self.panic = False
		else:
			self.panic = True

		self.score = true_eval(self.color, self.board)

		(v, m, e) = alphabeta((self.color, self.panic, self.board, 3, float("-inf"), float("inf"), True))
		self.expectedScore = v
		self.expectedEnemy = e
		if m in move_actions:
			print(m)
			return m
		else:
			print("Illegal move requested")
			print(m)
			return None

		#return random.choice(move_actions + [None])

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if taken_move is not None:
			self.board.push(taken_move)
			if requested_move is not taken_move:
				self.interestingTile = taken_move.to_square
		else:
			if requested_move is not taken_move:
				self.interestingTile = requested_move.to_square

		print ("MonteAlpha2:\t End move ", self.moveNum, " -- approx ", '{:06.2f}'.format(self.approxTime), " seconds left || Score: ", '{:06.1f}'.format(self.score), "Expected Score: ", '{:06.1f}'.format(self.expectedScore))
		if self.panic:
			print("\tWe lost track of their king.")

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
